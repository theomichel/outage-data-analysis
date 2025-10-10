// Mock HTTP server for testing utility API calls

export interface MockServer {
  mockResponse: (url: string, responseFile: string) => void;
  mockJsonResponse: (url: string, data: any) => void;
  restore: () => void;
}

export function createMockServer(verbose = false): MockServer {
  const mockResponses = new Map<string, { type: 'file' | 'json', data: any }>();
  const originalFetch = globalThis.fetch;

  // Override global fetch
  globalThis.fetch = async (input: string | URL | Request, init?: RequestInit): Promise<Response> => {
    const url = typeof input === 'string' ? input : input instanceof URL ? input.toString() : input.url;

    // Check if we have a mock for this URL
    for (const [mockUrl, mockData] of mockResponses.entries()) {
      if (url.includes(mockUrl)) {
        if (verbose) console.log(`[MockServer] Intercepted: ${url}`);

        if (mockData.type === 'file') {
          try {
            const fileContent = await Deno.readTextFile(mockData.data);
            return new Response(fileContent, {
              status: 200,
              headers: { 'Content-Type': 'application/json' },
            });
          } catch (e) {
            console.error(`[MockServer] Error reading mock file: ${mockData.data}`, e);
            return new Response('Mock file not found', { status: 500 });
          }
        } else {
          // JSON response
          return new Response(JSON.stringify(mockData.data), {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          });
        }
      }
    }

    // If no mock found, use original fetch (silently for DB calls)
    return originalFetch(input, init);
  };

  return {
    mockResponse: (url: string, responseFile: string) => {
      if (verbose) console.log(`[MockServer] Mock: ${url} -> ${responseFile}`);
      mockResponses.set(url, { type: 'file', data: responseFile });
    },

    mockJsonResponse: (url: string, data: any) => {
      if (verbose) console.log(`[MockServer] Mock: ${url} -> JSON data`);
      mockResponses.set(url, { type: 'json', data });
    },

    restore: () => {
      globalThis.fetch = originalFetch;
      mockResponses.clear();
    },
  };
}

// Convenience functions for specific utilities
export function mockPgeApi(mockServer: MockServer, responseFile: string): void {
  mockServer.mockResponse('pge.esriemcs.com', responseFile);
}

export function mockPseApi(mockServer: MockServer, responseFile: string): void {
  mockServer.mockResponse('pse.com/api/sitecore/OutageMap', responseFile);
}

export function mockSclApi(mockServer: MockServer, responseFile: string): void {
  mockServer.mockResponse('utilisocial.io/datacapable/v2/p/scl', responseFile);
}

export function mockSnopudApi(mockServer: MockServer, responseFile: string): void {
  mockServer.mockResponse('outagemap.snopud.com', responseFile);
}
