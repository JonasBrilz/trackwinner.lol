import { redirect } from "next/navigation";

export default function LegacyAuswertungRedirect(): never {
  redirect("/report");
}
