import BrandMark from "./BrandMark";

export default function Navbar() {
  return (
    <header className="w-full border-b border-line/60 bg-canvas/80 backdrop-blur-sm sticky top-0 z-40">
      <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
        <BrandMark />

        <nav className="hidden md:flex items-center gap-8 text-[14px] text-ink/80">
          <a className="hover:text-ink" href="#">Pricing</a>
          <a className="hover:text-ink" href="#">Resources</a>
          <a className="hover:text-ink" href="#">Partnerships</a>
          <a className="hover:text-ink" href="#">Careers</a>
        </nav>

        <div className="w-px" />
      </div>
    </header>
  );
}
