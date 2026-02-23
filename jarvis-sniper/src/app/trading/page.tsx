import { redirect } from 'next/navigation';

export default function TradingRedirectPage() {
  redirect('/investments?tab=perps');
}
