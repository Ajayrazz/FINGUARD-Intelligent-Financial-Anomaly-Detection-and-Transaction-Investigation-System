import type { GraphNode } from '../api/types'

/** Concentric layout: the centre account in the middle, each depth level on its own ring. */
export function ringLayout(nodes: GraphNode[]): Record<number, { x: number; y: number }> {
  const byDepth = new Map<number, GraphNode[]>()
  for (const n of nodes) byDepth.set(n.depth, [...(byDepth.get(n.depth) ?? []), n])
  const pos: Record<number, { x: number; y: number }> = {}
  for (const [depth, group] of byDepth) {
    if (depth === 0) {
      for (const n of group) pos[n.id] = { x: 0, y: 0 }
      continue
    }
    const radius = 190 * depth + Math.max(0, group.length - 8) * 6
    group.forEach((n, i) => {
      const angle = (2 * Math.PI * i) / group.length - Math.PI / 2
      pos[n.id] = { x: Math.round(radius * Math.cos(angle)), y: Math.round(radius * Math.sin(angle)) }
    })
  }
  return pos
}

export const FINDING_LABEL: Record<string, string> = {
  cycle: 'Circular flow',
  chain: 'Rapid chain',
  fan_in: 'Fan-in',
  fan_out: 'Fan-out',
  shared_beneficiary: 'Shared beneficiaries',
  dense_cluster: 'Dense cluster',
}
