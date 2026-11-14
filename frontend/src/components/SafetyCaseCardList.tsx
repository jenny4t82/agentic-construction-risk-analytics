import type { SafetyCaseResponse } from '../types';
import { SafetyCaseCard } from './SafetyCaseCard';

export function SafetyCaseCardList({ items, onOpen }: { items: SafetyCaseResponse[]; onOpen: (item: SafetyCaseResponse) => void }) {
  return <div aria-label="Safety cases" className="space-y-3">{items.map((item) => <SafetyCaseCard key={item.case_id} item={item} onOpen={() => onOpen(item)} />)}</div>;
}
