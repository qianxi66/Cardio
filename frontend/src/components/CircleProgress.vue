<script setup lang="tsx">
import { computed, type CSSProperties, type VNode } from 'vue'
import { stateColors } from '@/config'
import { get } from 'node_modules/axios/index.cjs'
const props = withDefaults(
  defineProps<{
    percent: number
    color: string
  }>(),
  {
    percent: 0
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
  if (strokeColor === undefined) {
    pathStyle.stroke = `url(#header-shape-gradient)`
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
const getArrow = (strokeWidth: number) => {
  const angle = -Math.PI
  const length = radius // Length of the arrow from the center of the circle
  const arrowLength = 40 // Actual length of the arrowhead
  const arrowWidth = 6 // Width of the base of the triangle arrowhead

  // Coordinates for the tip of the arrow
  const tipX = radius + strokeWidth / 2 + length * Math.cos(angle)
  const tipY = radius + strokeWidth / 2 + length * Math.sin(angle)

  // Coordinates for the base of the arrow, adjusting for the width
  const leftX = radius + strokeWidth / 2 + arrowWidth * Math.cos(angle + Math.PI / 2)
  const leftY = radius + strokeWidth / 2 + arrowWidth * Math.sin(angle + Math.PI / 2)
  const rightX = radius + strokeWidth / 2 + arrowWidth * Math.cos(angle - Math.PI / 2)
  const rightY = radius + strokeWidth / 2 + arrowWidth * Math.sin(angle - Math.PI / 2)

  return (
    <polygon
      angle={angle}
      points={`${tipX},${tipY} ${leftX},${leftY} ${rightX},${rightY}`}
      fill="black"
      style={{
        transformOrigin: `${radius + strokeWidth / 2}px ${radius + strokeWidth / 2}px`,
        transform: `rotate(${(props.percent / 100) * 180}deg)`
      }}
    />
  )
}

const strokeWidth = 20
const radius = 50
const Circle = computed(() => {
  return (
    <svg viewBox={`0 0 ${radius * 2 + strokeWidth} ${radius * 2 + strokeWidth}`}>
      <defs>
        <linearGradient
          id="header-shape-gradient"
          style={{
            '--color-1': `color-mix(in srgb, ${props.color}, white 80%)`,
            '--color-2': `color-mix(in srgb, ${props.color}, white 70%)`,
            '--color-3': `color-mix(in srgb, ${props.color}, white 50%)`,
            '--color-4': `color-mix(in srgb, ${props.color}, white 10%)`,
            '--color-5': props.color
          }}
        >
          <stop offset="0%" stop-color="var(--color-1)" />
          <stop offset="15%" stop-color="var(--color-2)" />
          <stop offset="50%" stop-color="var(--color-3)" />
          <stop offset="85%" stop-color="var(--color-4)" />
          <stop offset="100%" stop-color="var(--color-5)" />
        </linearGradient>
      </defs>
      {getPath(100, radius * 2, strokeWidth, '#f0f0f0')}
      {getPath(props.percent, radius * 2, strokeWidth)}
      {getArrow(strokeWidth)}
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
