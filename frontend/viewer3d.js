/* Dependency-free interactive isometric concept viewer. */
function drawBuilding(canvas) {
  const context = canvas.getContext("2d");
  if (!context) return;
  const bounds = canvas.getBoundingClientRect();
  if (!bounds.width || !bounds.height) return;
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  canvas.width = Math.round(bounds.width * dpr);
  canvas.height = Math.round(bounds.height * dpr);
  context.setTransform(dpr, 0, 0, dpr, 0, 0);
  const width = bounds.width;
  const height = bounds.height;
  context.clearRect(0, 0, width, height);

  const floors = Math.max(1, Math.min(20, Number(canvas.dataset.floors || 1)));
  const area = Math.max(20, Number(canvas.dataset.area || 100));
  const footprint = Math.sqrt(area / floors);
  const aspect = 1.12;
  const w = Math.sqrt(footprint * footprint * aspect) / Math.max(1, footprint / 10);
  const d = w / aspect;
  const h = floors * 2.05;
  const rotation = Number(canvas.dataset.rotation || 0.65);
  const unitScale = Math.min(width / (w + d + 1), (height - 28) / (h + (w + d) * 0.26)) * 0.86;
  const cx = width / 2;
  const floorY = height * 0.78;
  const sin = Math.sin(rotation);
  const cos = Math.cos(rotation);
  const project = (x, y, z) => {
    const xr = x * cos + z * sin;
    const zr = -x * sin + z * cos;
    return { x: cx + (xr - zr) * unitScale * 0.63, y: floorY + (xr + zr) * unitScale * 0.30 - y * unitScale * 0.76, depth: zr };
  };
  const hw = w / 2;
  const hd = d / 2;
  const makeFace = (coords, fill, stroke = "rgba(53,83,64,.46)") => {
    const points = coords.map(([x, y, z]) => project(x, y, z));
    context.beginPath();
    context.moveTo(points[0].x, points[0].y);
    points.slice(1).forEach((point) => context.lineTo(point.x, point.y));
    context.closePath();
    context.fillStyle = fill;
    context.fill();
    context.strokeStyle = stroke;
    context.lineWidth = 1.15;
    context.stroke();
    return points;
  };

  context.save();
  context.fillStyle = "rgba(43,78,54,.10)";
  context.beginPath();
  context.ellipse(cx, floorY + 7, Math.min(width * .30, 120), 14, 0, 0, Math.PI * 2);
  context.fill();
  context.restore();

  const front = [[-hw, 0, -hd], [hw, 0, -hd], [hw, h, -hd], [-hw, h, -hd]];
  const side = [[hw, 0, -hd], [hw, 0, hd], [hw, h, hd], [hw, h, -hd]];
  const top = [[-hw, h, -hd], [hw, h, -hd], [hw, h, hd], [-hw, h, hd]];
  const visibleFaces = [
    { coords: front, fill: "#dbe7d6" },
    { coords: side, fill: "#b8cbb8" },
  ].sort((a, b) => {
    const depthA = a.coords.reduce((sum, p) => sum + project(...p).depth, 0) / 4;
    const depthB = b.coords.reduce((sum, p) => sum + project(...p).depth, 0) / 4;
    return depthB - depthA;
  });
  visibleFaces.forEach((face) => makeFace(face.coords, face.fill));
  makeFace(top, "#edf2e6");

  // Front elevation openings and level lines.
  for (let level = 1; level < floors; level += 1) {
    const y = (h / floors) * level;
    const line = [[-hw, y, -hd - .006], [hw, y, -hd - .006]].map(([x, yy, z]) => project(x, yy, z));
    context.beginPath(); context.moveTo(line[0].x, line[0].y); context.lineTo(line[1].x, line[1].y);
    context.strokeStyle = "rgba(51,80,60,.32)"; context.lineWidth = 1; context.stroke();
  }
  const windowsPerFloor = Math.min(4, Math.max(2, Math.round(w / 2.2)));
  for (let floor = 0; floor < floors; floor += 1) {
    const yBottom = floor * (h / floors) + .58;
    const yTop = Math.min((floor + 1) * (h / floors) - .48, h - .24);
    for (let index = 0; index < windowsPerFloor; index += 1) {
      const x = -hw + ((index + 1) / (windowsPerFloor + 1)) * w;
      const corners = [[x - .22, yBottom, -hd - .01], [x + .22, yBottom, -hd - .01], [x + .22, yTop, -hd - .01], [x - .22, yTop, -hd - .01]].map(([xx, yy, z]) => project(xx, yy, z));
      context.beginPath(); context.moveTo(corners[0].x, corners[0].y); corners.slice(1).forEach((point) => context.lineTo(point.x, point.y)); context.closePath();
      context.fillStyle = "#a9c6b4"; context.fill(); context.strokeStyle = "rgba(49,82,60,.45)"; context.lineWidth = .8; context.stroke();
    }
  }
  canvas.onpointerdown = (event) => { canvas.dataset.dragging = "true"; canvas.dataset.pointerX = String(event.clientX); canvas.setPointerCapture?.(event.pointerId); };
  canvas.onpointermove = (event) => {
    if (canvas.dataset.dragging !== "true") return;
    const prior = Number(canvas.dataset.pointerX || event.clientX);
    const next = Number(canvas.dataset.rotation || 0.65) + (event.clientX - prior) * .01;
    canvas.dataset.pointerX = String(event.clientX);
    canvas.dataset.rotation = String(next);
    window.requestAnimationFrame(() => drawBuilding(canvas));
  };
  canvas.onpointerup = () => { canvas.dataset.dragging = "false"; };
  canvas.onpointercancel = () => { canvas.dataset.dragging = "false"; };
}


window.drawBuilding = drawBuilding;
