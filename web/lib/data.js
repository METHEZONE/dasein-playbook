import raw from '../data/results.json';
export const data = raw;
export const sysById = Object.fromEntries([...raw.systems, ...(raw.extra_systems || [])].map((s) => [s.id, s]));
export const HUMAN = { id: 'Human', name: 'Human', vendor: 'human' };
