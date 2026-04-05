export default function TopBar() {
  return (
    <div className="fixed top-0 left-0 right-0 z-50 flex h-10 items-center bg-[#0F1F3D] px-5">
      <span className="text-sm font-bold tracking-tight text-white">
        bon<span className="text-[#F5A623]">UP</span>
        <span className="ml-2 text-[11px] font-normal uppercase tracking-widest text-white/50">
          Blackboard
        </span>
      </span>
      <span className="ml-3 text-[11px] italic text-white/35">
        Keeping the world together through clear contracting
      </span>
    </div>
  )
}
