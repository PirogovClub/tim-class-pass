import { RuleConditions } from '@/components/rule/RuleConditions';
export function RuleExceptions({ title, items }: { title: string; items: string[] }) { return <RuleConditions title={title} items={items} />; }
