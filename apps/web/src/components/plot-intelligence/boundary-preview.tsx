import type { CoordinateSpace } from "@compose-ai/shared";

interface BoundaryPreviewProps {
  coordinateSpace: CoordinateSpace;
  vertices: { x: string; y: string }[];
}

export function BoundaryPreview({ coordinateSpace, vertices }: BoundaryPreviewProps) {
  const points = vertices
    .map((vertex) => ({ x: Number(vertex.x), y: Number(vertex.y) }))
    .filter((point) => Number.isFinite(point.x) && Number.isFinite(point.y));
  if (points.length < 3) {
    return (
      <div className="flex aspect-[16/10] items-center justify-center border border-dashed border-border bg-secondary/25 px-5 text-center text-sm text-muted-foreground">
        Add three or more valid vertices to preview the plot boundary.
      </div>
    );
  }
  const xs = points.map((point) => point.x);
  const ys = points.map((point) => point.y);
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  const span = Math.max(maxX - minX, maxY - minY, 1);
  const padding = 18;
  const svgPoints = points
    .map((point) => {
      const x = padding + ((point.x - minX) / span) * (100 - padding * 2);
      const y = 100 - padding - ((point.y - minY) / span) * (100 - padding * 2);
      return `${x},${y}`;
    })
    .join(" ");

  return (
    <figure className="overflow-hidden border border-border bg-secondary/20">
      <svg
        aria-label={`Static ${coordinateSpace === "wgs84" ? "WGS84" : "local"} plot boundary preview`}
        className="block aspect-[16/10] w-full"
        role="img"
        viewBox="0 0 100 100"
      >
        <rect fill="currentColor" fillOpacity="0.025" height="100" width="100" x="0" y="0" />
        <polygon
          fill="currentColor"
          fillOpacity="0.14"
          points={svgPoints}
          stroke="currentColor"
          strokeWidth="1.5"
        />
        {points.map((point, index) => {
          const x = padding + ((point.x - minX) / span) * (100 - padding * 2);
          const y = 100 - padding - ((point.y - minY) / span) * (100 - padding * 2);
          return <circle cx={x} cy={y} fill="currentColor" key={index} r="1.8" />;
        })}
        <path d="M 87 18 L 87 33 M 82 23 L 87 18 L 92 23" fill="none" stroke="currentColor" strokeWidth="1.5" />
        <text fill="currentColor" fontSize="7" textAnchor="middle" x="87" y="13">
          N
        </text>
      </svg>
      <figcaption className="border-t border-border px-3 py-2 text-xs text-muted-foreground">
        Static preview only. Plot editing remains form-based in Phase 5A.
      </figcaption>
    </figure>
  );
}
