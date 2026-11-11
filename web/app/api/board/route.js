import { board } from '../../../lib/votes';
export const dynamic = 'force-dynamic';
export const GET = async () => Response.json(await board());
