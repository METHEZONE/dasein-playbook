import { siOpenai, siAnthropic } from 'simple-icons';
export default function Logo({ vendor }) {
  if (vendor === 'tell') return <span className="tdot" aria-label="Dasein" />;
  const i = vendor === 'openai' ? siOpenai : vendor === 'anthropic' ? siAnthropic : null;
  if (!i) return <span className="logo" />;
  return <svg className="logo" viewBox="0 0 24 24" role="img" aria-label={i.title}><path d={i.path} fill="currentColor" /></svg>;
}
