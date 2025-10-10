// Geometry utilities - smallest enclosing circle algorithm

type Point = [number, number];
type Circle = [number, number, number]; // [centerX, centerY, radius]

function distance(a: Point, b: Point): number {
  const dx = a[0] - b[0];
  const dy = a[1] - b[1];
  return Math.sqrt(dx * dx + dy * dy);
}

function isInCircle(point: Point, circle: Circle | null): boolean {
  if (!circle) return false;
  const [cx, cy, r] = circle;
  return distance(point, [cx, cy]) <= r + 1e-12;
}

function circleFromTwoPoints(a: Point, b: Point): Circle {
  const cx = (a[0] + b[0]) / 2.0;
  const cy = (a[1] + b[1]) / 2.0;
  const r = distance(a, b) / 2.0;
  return [cx, cy, r];
}

function circleFromThreePoints(a: Point, b: Point, c: Point): Circle | null {
  const [ax, ay] = a;
  const [bx, by] = b;
  const [cx, cy] = c;

  const d = 2 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by));
  if (Math.abs(d) < 1e-18) return null;

  const ax2ay2 = ax * ax + ay * ay;
  const bx2by2 = bx * bx + by * by;
  const cx2cy2 = cx * cx + cy * cy;

  const ux = (ax2ay2 * (by - cy) + bx2by2 * (cy - ay) + cx2cy2 * (ay - by)) / d;
  const uy = (ax2ay2 * (cx - bx) + bx2by2 * (ax - cx) + cx2cy2 * (bx - ax)) / d;
  const r = distance([ux, uy], a);

  return [ux, uy, r];
}

export function smallestEnclosingCircle(arrayOfArraysOfPoints: Point[][]): Circle {
  const normalized: Point[] = [];

  for (const pointsLonLat of arrayOfArraysOfPoints) {
    for (const p of pointsLonLat || []) {
      if (p === null || p === undefined) continue;
      try {
        const lon = p[0];
        const lat = p[1];
        if (typeof lon === 'number' && typeof lat === 'number' && !isNaN(lon) && !isNaN(lat)) {
          normalized.push([lon, lat]);
        }
      } catch {
        continue;
      }
    }
  }

  // De-duplicate
  const seen = new Set<string>();
  const points: Point[] = [];
  for (const pt of normalized) {
    const key = `${pt[0]},${pt[1]}`;
    if (!seen.has(key)) {
      seen.add(key);
      points.push(pt);
    }
  }

  if (points.length === 0) return [0.0, 0.0, 0.0];
  if (points.length === 1) return [points[0][0], points[0][1], 0.0];

  // Incremental algorithm
  let c: Circle | null = null;
  for (let i = 0; i < points.length; i++) {
    const p = points[i];
    if (c === null || !isInCircle(p, c)) {
      c = [p[0], p[1], 0.0];
      for (let j = 0; j < i; j++) {
        const q = points[j];
        if (!isInCircle(q, c)) {
          c = circleFromTwoPoints(p, q);
          for (let k = 0; k < j; k++) {
            const r = points[k];
            if (!isInCircle(r, c)) {
              const c3 = circleFromThreePoints(p, q, r);
              if (c3 !== null) {
                c = c3;
              }
            }
          }
        }
      }
    }
  }

  return c || [0.0, 0.0, 0.0];
}

export function calculateExpectedLengthMinutes(
  updateTime: string | Date | null,
  estRestorationTime: string | Date | null
): number | null {
  try {
    if (!updateTime || !estRestorationTime) return null;

    const updateDate = typeof updateTime === 'string' ? new Date(updateTime) : updateTime;
    const restDate = typeof estRestorationTime === 'string' ? new Date(estRestorationTime) : estRestorationTime;

    if (isNaN(updateDate.getTime()) || isNaN(restDate.getTime())) return null;

    const timeDiff = restDate.getTime() - updateDate.getTime();
    return Math.floor(timeDiff / 60000);
  } catch {
    return null;
  }
}

export function calculateElapsedMinutes(startTime: string | Date, currentTime: string | Date): number | null {
  try {
    const startDate = typeof startTime === 'string' ? new Date(startTime) : startTime;
    const currentDate = typeof currentTime === 'string' ? new Date(currentTime) : currentTime;

    if (isNaN(startDate.getTime()) || isNaN(currentDate.getTime())) return null;

    const timeDiff = currentDate.getTime() - startDate.getTime();
    return Math.floor(timeDiff / 60000);
  } catch {
    return null;
  }
}
