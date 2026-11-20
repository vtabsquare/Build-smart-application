import { useEffect, useRef } from 'react';

const WIDTH = 800;
const HEIGHT = 500;

function drawBuilding(context) {
  const project = ([x, y, z]) => [397 + (x - y) * 1.26, 323 + (x + y) * 0.49 - z];

  function path(points, fill, stroke, width = 1) {
    context.beginPath();
    points.map(project).forEach(([x, y], index) => {
      if (index === 0) context.moveTo(x, y);
      else context.lineTo(x, y);
    });
    if (fill) {
      context.closePath();
      context.fillStyle = fill;
      context.fill();
    }
    if (stroke) {
      context.strokeStyle = stroke;
      context.lineWidth = width;
      context.stroke();
    }
  }

  function volume(x, y, w, d, bottom, top, colors) {
    const a = [x, y, top], b = [x + w, y, top];
    const c = [x + w, y + d, top], e = [x, y + d, top];
    path([e, c, [x + w, y + d, bottom], [x, y + d, bottom], e], colors[0], '#4c9d9e');
    path([b, c, [x + w, y + d, bottom], [x + w, y, bottom], b], colors[1], '#3c707c');
    path([a, b, c, e, a], colors[2], '#8acac0');
  }

  const glow = context.createRadialGradient(400, 266, 8, 400, 266, 290);
  glow.addColorStop(0, '#278a885c');
  glow.addColorStop(1, '#278a8800');
  context.fillStyle = glow;
  context.fillRect(0, 0, WIDTH, HEIGHT);

  for (let mark = -160; mark <= 160; mark += 20) {
    path([[mark, -160, 0], [mark, 160, 0]], null, '#5fe6d427');
    path([[-160, mark, 0], [160, mark, 0]], null, '#5fe6d427');
  }
  path([[-139, -110, 1], [125, -110, 1], [125, 110, 1], [-139, 110, 1], [-139, -110, 1]], '#08303aab', '#6de9d8a0');
  volume(-104, -76, 211, 158, 4, 13, ['#1b4953', '#122d3c', '#2c6269']);
  volume(-85, -65, 173, 131, 13, 22, ['#39747b', '#193d4b', '#619899']);

  for (let floor = 0; floor < 4; floor += 1) {
    const z = 22 + floor * 47;
    const x = floor === 3 ? -43 : -70;
    const y = -56;
    const w = floor === 3 ? 108 : 145;
    const depth = floor === 3 ? 86 : 107;
    const edge = y + depth;
    const side = x + w;
    volume(x, y, w, depth, z, z + 39, ['#23535e', '#102c3f', '#5c858b']);
    for (let windowX = x + 9; windowX < side - 14; windowX += 19) {
      const warm = (windowX + floor * 7) % 3 === 0;
      path([[windowX, edge + 0.3, z + 6], [windowX + 13, edge + 0.3, z + 6], [windowX + 13, edge + 0.3, z + 33], [windowX, edge + 0.3, z + 33], [windowX, edge + 0.3, z + 6]], warm ? '#c79768' : '#0a2534', warm ? '#ffe1a5' : '#73b0b2');
    }
    for (let windowY = y + 8; windowY < edge - 14; windowY += 19) {
      path([[side + 0.3, windowY, z + 6], [side + 0.3, windowY + 12, z + 6], [side + 0.3, windowY + 12, z + 33], [side + 0.3, windowY, z + 33], [side + 0.3, windowY, z + 6]], '#122234', '#408b9b');
    }
    volume(x - 6, y - 5, w + 12, depth + 10, z + 37, z + 46, ['#80b5ab', '#35616a', '#76aaa9']);
  }

  volume(-32, -44, 58, 47, 209, 224, ['#476e75', '#234653', '#81aaa6']);
  path([[-131, 121, 0], [124, 121, 0]], null, '#80f3dd8c');
  path([[-131, 112, 0], [-131, 130, 0]], null, '#80f3dd8c');
  path([[124, 112, 0], [124, 130, 0]], null, '#80f3dd8c');
  path([[117, -100, 0], [117, -100, 224], [-27, -100, 224]], null, '#80f3dd62');
}

export default function BuildingStudy() {
  const canvas = useRef(null);

  useEffect(() => {
    const context = canvas.current.getContext('2d');
    if (context) drawBuilding(context);
  }, []);

  return (
    <div className="building-study" aria-hidden="true">
      <canvas ref={canvas} width={WIDTH} height={HEIGHT} />
      <div className="building-study-scan" />
    </div>
  );
}
