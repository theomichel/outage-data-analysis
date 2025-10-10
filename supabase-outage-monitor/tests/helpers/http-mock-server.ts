// HTTP mock server for E2E testing
// This server runs on localhost and serves test fixture files to the edge function

import { Server } from 'https://deno.land/std@0.224.0/http/server.ts';

export interface MockRoute {
  path: string;
  fixtureFile: string;
}

export interface HttpMockServer {
  setRoute: (path: string, fixtureFile: string) => void;
  getUrl: (path: string) => string;
  shutdown: () => Promise<void>;
}

// Transform PGE fixture timestamps to be relative to current time
function transformPgeFixtureTimes(fixtureContent: string, fixtureFilename: string): string {
  // Extract original snapshot time from filename (e.g., "2025-08-29T224647")
  const match = fixtureFilename.match(/(\d{4}-\d{2}-\d{2}T\d{6})/);
  if (!match) {
    console.warn('[HttpMockServer] Could not extract timestamp from filename, serving unmodified');
    return fixtureContent;
  }

  // Parse the original snapshot time (format: 2025-08-29T224647)
  const timestampStr = match[1];
  const year = timestampStr.substring(0, 4);
  const month = timestampStr.substring(5, 7);
  const day = timestampStr.substring(8, 10);
  const hour = timestampStr.substring(11, 13);
  const minute = timestampStr.substring(13, 15);
  const second = timestampStr.substring(15, 17);

  const originalSnapshotTime = new Date(`${year}-${month}-${day}T${hour}:${minute}:${second}Z`);
  const currentTime = new Date();

  // Calculate offset in milliseconds
  const timeOffset = currentTime.getTime() - originalSnapshotTime.getTime();

  console.log(`[HttpMockServer] Adjusting fixture times: original=${originalSnapshotTime.toISOString()}, current=${currentTime.toISOString()}, offset=${timeOffset}ms`);

  // Parse JSON and adjust all timestamp fields
  const data = JSON.parse(fixtureContent);

  if (data.features && Array.isArray(data.features)) {
    for (const feature of data.features) {
      if (feature.attributes) {
        // Adjust PGE timestamp fields (in milliseconds)
        if (feature.attributes.OUTAGE_START) {
          feature.attributes.OUTAGE_START += timeOffset;
        }
        if (feature.attributes.CURRENT_ETOR) {
          feature.attributes.CURRENT_ETOR += timeOffset;
        }
        if (feature.attributes.LAST_UPDATE) {
          feature.attributes.LAST_UPDATE += timeOffset;
        }
      }
    }
  }

  return JSON.stringify(data);
}

export async function startHttpMockServer(port = 9999): Promise<HttpMockServer> {
  const routes = new Map<string, string>();

  const handler = async (req: Request): Promise<Response> => {
    const url = new URL(req.url);
    const path = url.pathname;

    console.log(`[HttpMockServer] Request: ${path} (full URL: ${req.url})`);

    // Check if we have a mock for this path
    if (routes.has(path)) {
      const fixtureFile = routes.get(path)!;

      try {
        let content = await Deno.readTextFile(fixtureFile);

        // Transform PGE fixture timestamps
        if (path.includes('/mock/pge')) {
          content = transformPgeFixtureTimes(content, fixtureFile);
        }

        console.log(`[HttpMockServer] Serving fixture: ${fixtureFile}`);
        return new Response(content, {
          status: 200,
          headers: {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
          },
        });
      } catch (error) {
        console.error(`[HttpMockServer] Error reading fixture file ${fixtureFile}:`, error);
        return new Response(`Mock fixture not found: ${fixtureFile}`, { status: 500 });
      }
    }

    // No mock found
    console.log(`[HttpMockServer] No mock for path: ${path}, available routes:`, Array.from(routes.keys()));
    return new Response(`No mock configured for ${path}`, { status: 404 });
  };

  // Start the server
  const abortController = new AbortController();

  const serverPromise = Deno.serve({
    port,
    signal: abortController.signal,
    onListen: ({ hostname, port }) => {
      console.log(`[HttpMockServer] Listening on http://${hostname}:${port}`);
    },
  }, handler);

  // Give the server a moment to start
  await new Promise(resolve => setTimeout(resolve, 100));

  return {
    setRoute: (path: string, fixtureFile: string) => {
      routes.set(path, fixtureFile);
      console.log(`[HttpMockServer] Route configured: ${path} -> ${fixtureFile}`);
    },

    getUrl: (path: string) => {
      return `http://localhost:${port}${path}`;
    },

    shutdown: async () => {
      console.log('[HttpMockServer] Shutting down...');
      abortController.abort();
      try {
        await serverPromise;
      } catch (error) {
        // Expected error when aborting - ignore
        if (error instanceof Error && error.name !== 'AbortError') {
          console.error('[HttpMockServer] Error during shutdown:', error);
        }
      }
      console.log('[HttpMockServer] Shutdown complete');
    },
  };
}

// Convenience function for PGE mock
export function mockPgeRoute(server: HttpMockServer, fixtureFile: string): string {
  const path = '/mock/pge';
  server.setRoute(path, fixtureFile);
  return server.getUrl(path);
}

// Convenience function for PSE mock
export function mockPseRoute(server: HttpMockServer, fixtureFile: string): string {
  const path = '/mock/pse';
  server.setRoute(path, fixtureFile);
  return server.getUrl(path);
}

// Convenience function for SCL mock
export function mockSclRoute(server: HttpMockServer, fixtureFile: string): string {
  const path = '/mock/scl';
  server.setRoute(path, fixtureFile);
  return server.getUrl(path);
}

// Convenience function for SnoPUD mock
export function mockSnopudRoute(server: HttpMockServer, fixtureFile: string): string {
  const path = '/mock/snopud';
  server.setRoute(path, fixtureFile);
  return server.getUrl(path);
}
