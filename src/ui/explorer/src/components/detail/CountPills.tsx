interface CountPillsProps { counts: Array<{ label: string; value: number }>; }
export function CountPills({ counts }: CountPillsProps) { return <div className="flex flex-wrap gap-2">{counts.map((item) => <span key={item.label} className="rounded-full bg-slate-100 px-3 py-1 text-sm font-medium text-slate-700">{item.value} {item.label}</span>)}</div>; }
