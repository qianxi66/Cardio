<script setup lang="tsx">
import { computed, type CSSProperties, type VNode } from 'vue'
import { stateColors } from '@/config'
const props = withDefaults(
  defineProps<{
    percent: number
    color: string
    id: string
    autocolor?: boolean
    visible?: boolean
  }>(),
  {
    percent: 0,
    visible: true,
    autocolor: false
  }
)
const color = computed(() => {
  if (props.autocolor) {
    if (props.percent <= 0){
      return stateColors[0]
    } else if (props.percent <= 30){
      return stateColors[2]
    } else if (props.percent <= 60){
      return stateColors[3]
    } else if (props.percent <= 100){
      return stateColors[4]
    }
  }
  return props.color
})
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
    pathStyle.stroke = `url(#${props.id}-header-shape-gradient)`
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
          id={`${props.id}-header-shape-gradient`}
          style={{
            '--color-1': `color-mix(in srgb, ${color.value}, white 80%)`,
            '--color-2': `color-mix(in srgb, ${color.value}, white 70%)`,
            '--color-3': `color-mix(in srgb, ${color.value}, white 50%)`,
            '--color-4': `color-mix(in srgb, ${color.value}, white 10%)`,
            '--color-5': color.value
          }}
        >
          <stop offset="0%" stop-color="var(--color-1)" />
          <stop offset="15%" stop-color="var(--color-2)" />
          <stop offset="50%" stop-color="var(--color-3)" />
          <stop offset="85%" stop-color="var(--color-4)" />
          <stop offset="100%" stop-color="var(--color-5)" />
        </linearGradient>
      </defs>
      {props.visible && getPath(100, radius * 2, strokeWidth, '#e0e0e0')}
      {props.visible && props.percent != 0 && getPath(props.percent, radius * 2, strokeWidth)}
      {props.visible && props.percent != 0 && getArrow(strokeWidth)}
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
  bottom: 50%;
  left: 50%;
  transform: translateX(-50%) translateY(50%);
}
</style>
