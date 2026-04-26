import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from ..config import PEEC_API_KEY, PEEC_BASE_URL


def _extract_list(data: dict | list, *keys: str) -> list:
    if isinstance(data, list):
        return data
    for key in keys:
        if key in data and isinstance(data[key], list):
            return data[key]
    return []


class PeecClient:
    def __init__(self):
        self._client = httpx.AsyncClient(
            base_url=PEEC_BASE_URL,
            headers={"X-API-Key": PEEC_API_KEY},
            timeout=30.0,
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(min=1, max=10),
        retry=retry_if_exception_type(httpx.HTTPStatusError),
    )
    async def _get(self, path: str, **params) -> dict | list:
        resp = await self._client.get(path, params={k: v for k, v in params.items() if v is not None})
        resp.raise_for_status()
        return resp.json()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(min=1, max=10),
        retry=retry_if_exception_type(httpx.HTTPStatusError),
    )
    async def _post(self, path: str, project_id: str, body: dict) -> dict | list:
        resp = await self._client.post(
            path,
            params={"project_id": project_id},
            json=body,
        )
        resp.raise_for_status()
        return resp.json()

    async def list_projects(self) -> list[dict]:
        data = await self._get("/projects", limit=50)
        return _extract_list(data, "data", "projects", "items", "results")

    async def list_brands(self, project_id: str) -> list[dict]:
        data = await self._get("/brands", project_id=project_id, limit=100)
        return _extract_list(data, "data", "brands", "items", "results")

    async def list_prompts(self, project_id: str) -> list[dict]:
        all_prompts: list[dict] = []
        offset = 0
        limit = 200
        while True:
            data = await self._get("/prompts", project_id=project_id, limit=limit, offset=offset)
            page = _extract_list(data, "data", "prompts", "items", "results")
            all_prompts.extend(page)
            if len(page) < limit:
                break
            offset += limit
        return all_prompts

    async def brands_report(
        self, project_id: str, start_date: str, end_date: str
    ) -> list[dict]:
        data = await self._post(
            "/reports/brands",
            project_id=project_id,
            body={
                "project_id": project_id,
                "start_date": start_date,
                "end_date": end_date,
                "dimensions": ["prompt_id", "model_id"],
                "limit": 5000,
            },
        )
        return _extract_list(data, "data", "rows", "items", "results")

    async def list_chats(
        self, project_id: str, start_date: str, end_date: str
    ) -> tuple[list[dict], bool]:
        CAP = 5000
        all_chats: list[dict] = []
        offset = 0
        limit = 1000
        while len(all_chats) < CAP:
            data = await self._get(
                "/chats",
                project_id=project_id,
                start_date=start_date,
                end_date=end_date,
                limit=limit,
                offset=offset,
            )
            page = _extract_list(data, "data", "chats", "items", "results")
            all_chats.extend(page)
            if len(page) < limit:
                return all_chats, False
            offset += limit
        return all_chats[:CAP], True

    async def domains_report(
        self, project_id: str, start_date: str, end_date: str
    ) -> list[dict]:
        data = await self._post(
            "/reports/domains",
            project_id=project_id,
            body={
                "project_id": project_id,
                "start_date": start_date,
                "end_date": end_date,
                "dimensions": ["prompt_id"],
                "limit": 5000,
            },
        )
        return _extract_list(data, "data", "rows", "items", "results")

    async def domains_inventory(
        self, project_id: str, start_date: str, end_date: str, limit: int = 200
    ) -> list[dict]:
        """Top domains for a project — used by prep pipeline. Each row has
        domain, classification (UGC/LISTICLE/etc.), retrieval_count, citation_count,
        mentioned_brands[]."""
        data = await self._post(
            "/reports/domains",
            project_id=project_id,
            body={
                "project_id": project_id,
                "start_date": start_date,
                "end_date": end_date,
                "limit": limit,
            },
        )
        return _extract_list(data, "data", "rows", "items", "results")

    async def urls_by_chat(
        self,
        project_id: str,
        start_date: str,
        end_date: str,
        domains: list[str] | None = None,
        limit: int = 10000,
    ) -> list[dict]:
        """URL report grouped by chat_id. Each row has url, chat.id, mentioned_brands[],
        retrieval_count, citation_count. Used by prep pipeline to build per-chat brand maps."""
        body: dict = {
            "project_id": project_id,
            "start_date": start_date,
            "end_date": end_date,
            "dimensions": ["chat_id"],
            "limit": limit,
        }
        if domains:
            body["filters"] = [{"field": "domain", "operator": "in", "values": domains}]
        data = await self._post(
            "/reports/urls",
            project_id=project_id,
            body=body,
        )
        return _extract_list(data, "data", "rows", "items", "results")

    async def urls_report(
        self, project_id: str, start_date: str, end_date: str
    ) -> list[dict]:
        data = await self._post(
            "/reports/urls",
            project_id=project_id,
            body={
                "project_id": project_id,
                "start_date": start_date,
                "end_date": end_date,
                "dimensions": ["prompt_id"],
                "limit": 5000,
            },
        )
        return _extract_list(data, "data", "rows", "items", "results")

    async def close(self):
        await self._client.aclose()
