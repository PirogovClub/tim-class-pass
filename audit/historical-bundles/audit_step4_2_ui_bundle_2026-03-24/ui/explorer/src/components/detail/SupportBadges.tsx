import { Badge } from '@/components/ui/badge';
import { formatConfidence } from '@/lib/utils/format';
import { supportBasisLabel } from '@/lib/utils/badges';

interface SupportBadgesProps { supportBasis?: string | null; evidenceRequirement?: string | null; teachingMode?: string | null; confidenceScore?: number | null; }
export function SupportBadges({ supportBasis, evidenceRequirement, teachingMode, confidenceScore }: SupportBadgesProps) {
  const items = [supportBasisLabel(supportBasis), evidenceRequirement ? `Evidence: ${evidenceRequirement}` : null, teachingMode ? `Mode: ${teachingMode}` : null, formatConfidence(confidenceScore)];
  return <div className="flex flex-wrap gap-2">{items.filter(Boolean).map((item) => <Badge key={item} className="border-slate-200 bg-white text-slate-700">{item}</Badge>)}</div>;
}
