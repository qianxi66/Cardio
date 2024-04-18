<script setup lang="tsx">
import { computed, type CSSProperties, type VNode } from 'vue'
import { stateColors } from '@/config'
import { get } from 'node_modules/axios/index.cjs'
const props = withDefaults(
  defineProps<{
    percent: number
    limits?: number[]
  }>(),
  {
    percent: 0,
    limits: () => [0, 0, 50, 60]
  }
)
function getPath(
  percent: number,
  viewBoxWidth: number,
  strokeWidth: number,
  strokeColor?: string
): VNode {
  const offsetDegree = 0
  const gapDegree = 160
  const radius = 50
  const beginPositionX = 0
  const beginPositionY = radius
  const endPositionX = 0
  const endPositionY = 2 * radius
  const centerX = 50 + strokeWidth / 2
  const pathString = `M ${centerX},${centerX} m ${beginPositionX},${beginPositionY}
      a ${radius},${radius} 0 1 1 ${endPositionX},${-endPositionY}
      a ${radius},${radius} 0 1 1 ${-endPositionX},${endPositionY}`
  const len = Math.PI * 2 * radius
  const pathStyle: CSSProperties = {
    stroke: strokeColor,
    strokeDasharray: `${(percent / 100) * (len - gapDegree)}px ${viewBoxWidth * 8}px`,
    strokeDashoffset: `-${gapDegree / 2}px`,
    transformOrigin: offsetDegree ? 'center' : undefined,
    transform: offsetDegree ? `rotate(${offsetDegree}deg)` : undefined
  }
  return (
    <g>
      <path
        d={pathString}
        stroke-width={strokeWidth}
        stroke-linecap="round"
        fill="none"
        style={pathStyle}
      />
    </g>
  )
}
const strokeWidth = 20
const viewBoxSize = 50
const Circle = computed(() => {
  return (
    <svg viewBox={`0 0 ${viewBoxSize * 2 + strokeWidth} ${viewBoxSize + strokeWidth}`}>
      {getPath(100, viewBoxSize * 2, strokeWidth, '#f0f0f0')}
      {[1, 2, 3]
        .map((state) => {
          if (props.percent > props.limits[state]) {
            return getPath(props.percent, viewBoxSize * 2, strokeWidth, stateColors[state])
          } else {
            return false
          }
        })
        .filter((x) => x)
        .slice(-1)}
    </svg>
  )
})
</script>
<template>
  <div class="circle">
    <Circle></Circle>
    <div class="content">
      <slot></slot>
    </div>
  </div>
</template>
<style scoped lang="scss">
.circle {
  position: relative;
}
.content {
  position: absolute;
  bottom: 10%;
  left: 50%;
  transform: translateX(-50%);
}
</style>
