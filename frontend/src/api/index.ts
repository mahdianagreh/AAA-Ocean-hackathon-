import { DATA_SOURCE, type ApiClient } from './client';
import { fixtureClient } from './fixtures';
import { httpClient } from './http';

/** The single place the implementation is chosen. Components import `api()` and
 *  never learn which one they got — that is the whole point of the boundary. */
let client: ApiClient | null = null;

export function api(): ApiClient {
  client ??= DATA_SOURCE === 'http' ? httpClient() : fixtureClient();
  return client;
}

/** Tests swap the implementation without touching a component. */
export function setApiForTests(c: ApiClient | null): void {
  client = c;
}

export type { ApiClient } from './client';
export { DATA_SOURCE, API_BASE } from './client';
