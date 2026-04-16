// ============================================================================
// Camelot Wheel
// ============================================================================

const CAMELOT_MAP = {
  '1A': 'Abm', '1B': 'B',
  '2A': 'Ebm', '2B': 'F#',
  '3A': 'Bbm', '3B': 'Db',
  '4A': 'Fm', '4B': 'Ab',
  '5A': 'Cm', '5B': 'Eb',
  '6A': 'Gm', '6B': 'Bb',
  '7A': 'Dm', '7B': 'F',
  '8A': 'Am', '8B': 'C',
  '9A': 'Em', '9B': 'G',
  '10A': 'Bm', '10B': 'D',
  '11A': 'F#m', '11B': 'A',
  '12A': 'Dbm', '12B': 'E',
};

function createCamelotWheel(highlightKey) {
  const svg = document.getElementById('camelot-wheel');
  if (!svg) return;

  svg.innerHTML = '';
  const size = 200;
  const center = size / 2;
  const outerRadius = 80;
  const innerRadius = 50;

  // Helper to calculate angle in degrees (0 = top, clockwise)
  const getAngle = (position) => {
    return (position - 1) * 30 - 90; // -90 to start at top, position 1 at top
  };

  // Helper to convert angle to radians and get point
  const getPoint = (angle, radius) => {
    const rad = (angle * Math.PI) / 180;
    return {
      x: center + radius * Math.cos(rad),
      y: center + radius * Math.sin(rad),
    };
  };

  // Draw outer ring (Major/B keys)
  for (let i = 1; i <= 12; i++) {
    const angle = getAngle(i);
    const p1 = getPoint(angle, outerRadius);
    const p2 = getPoint(angle + 30, outerRadius);
    const pc = getPoint(angle + 15, outerRadius - 10);

    const keyStr = `${i}B`;
    const isHighlighted = highlightKey === keyStr;
    const isCompatible = isCompatibleKey(highlightKey, keyStr);

    const color = isHighlighted ? '#8b5cf6' : (isCompatible ? '#34d399' : '#888');

    // Wedge path
    const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    const d = `M ${center} ${center} L ${p1.x} ${p1.y} A ${outerRadius} ${outerRadius} 0 0 1 ${p2.x} ${p2.y} Z`;
    path.setAttribute('d', d);
    path.setAttribute('fill', color);
    path.setAttribute('opacity', '0.3');
    path.setAttribute('stroke', color);
    path.setAttribute('stroke-width', '1');
    svg.appendChild(path);

    // Key text
    const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
    text.setAttribute('x', pc.x);
    text.setAttribute('y', pc.y);
    text.setAttribute('text-anchor', 'middle');
    text.setAttribute('dominant-baseline', 'middle');
    text.setAttribute('font-size', '11');
    text.setAttribute('font-weight', '600');
    text.setAttribute('fill', color);
    text.textContent = keyStr;
    svg.appendChild(text);
  }

  // Draw inner ring (Minor/A keys)
  for (let i = 1; i <= 12; i++) {
    const angle = getAngle(i);
    const p1 = getPoint(angle, innerRadius);
    const p2 = getPoint(angle + 30, innerRadius);
    const pc = getPoint(angle + 15, innerRadius + 10);

    const keyStr = `${i}A`;
    const isHighlighted = highlightKey === keyStr;
    const isCompatible = isCompatibleKey(highlightKey, keyStr);

    const color = isHighlighted ? '#8b5cf6' : (isCompatible ? '#34d399' : '#888');

    // Wedge path
    const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    const d = `M ${center} ${center} L ${p1.x} ${p1.y} A ${innerRadius} ${innerRadius} 0 0 1 ${p2.x} ${p2.y} Z`;
    path.setAttribute('d', d);
    path.setAttribute('fill', color);
    path.setAttribute('opacity', '0.3');
    path.setAttribute('stroke', color);
    path.setAttribute('stroke-width', '1');
    svg.appendChild(path);

    // Key text
    const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
    text.setAttribute('x', pc.x);
    text.setAttribute('y', pc.y);
    text.setAttribute('text-anchor', 'middle');
    text.setAttribute('dominant-baseline', 'middle');
    text.setAttribute('font-size', '11');
    text.setAttribute('font-weight', '600');
    text.setAttribute('fill', color);
    text.textContent = keyStr;
    svg.appendChild(text);
  }

  // Draw center circle
  const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
  circle.setAttribute('cx', center);
  circle.setAttribute('cy', center);
  circle.setAttribute('r', '10');
  circle.setAttribute('fill', '#2a2a3a');
  svg.appendChild(circle);
}

function isCompatibleKey(key1, key2) {
  if (!key1 || !key2 || key1 === key2) return false;

  // Extract number from key (1-12)
  const num1 = parseInt(key1);
  const num2 = parseInt(key2);

  // Compatible if same number (±1 position) or adjacent number
  const numDiff = Math.min(Math.abs(num1 - num2), 12 - Math.abs(num1 - num2));
  return numDiff === 1;
}

