import './globals.css';
import './home.css';
import { BRAND, TAGLINE } from '../lib/brand';
export const metadata = {
  title: BRAND,
  description: TAGLINE,
  metadataBase: new URL('https://dasein.heyarca.app'),
  openGraph: { title: BRAND, description: TAGLINE },
};
export const viewport = { width: 'device-width', initialScale: 1, viewportFit: 'cover', themeColor: '#ffffff' };
export default function Root({ children }) {
  return (<html lang="en"><head><link rel="preconnect" href="https://api.fontshare.com" crossOrigin="" /><link rel="stylesheet" href="https://api.fontshare.com/v2/css?f[]=satoshi@300,400,500,700&display=swap" /></head><body>{children}</body></html>);
}
