import Link from "next/link";

type BrandMarkProps = {
  className?: string;
};

export default function BrandMark({ className = "" }: BrandMarkProps) {
  return (
    <Link
      href="/home"
      className={`inline-flex items-center gap-3 ${className}`}
      aria-label="Back to home"
    >
      <svg
        width="30"
        height="20"
        viewBox="0 0 30 20"
        fill="none"
        aria-hidden="true"
      >
        <rect x="6" y="2" width="18" height="5" rx="2" fill="#000000" />
        <rect x="0" y="10" width="18" height="8" rx="2.5" fill="#000000" />
      </svg>
      <span className="font-medium text-[20px] tracking-tight text-ink leading-none">
        Peec AI
      </span>
    </Link>
  );
}
