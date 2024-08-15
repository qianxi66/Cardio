<script setup lang="tsx">
import { computed } from 'vue'

import { useDialog, useMessage } from 'naive-ui'
window.$message = useMessage();
console.log(window.$message);
console.log(123);
</script>

<template>
  <header>
    <div class="container header">
      <a
        class="title"
        href="#"
        style="color: inherit; text-decoration: none"
        @click.prevent="$router.push('/')"
      >
        Recover Dashboard
      </a>
      <div class="space"></div>
      <div style="margin-right: 20px"><n-button text color="#fff">123</n-button></div>
    </div>
  </header>
</template>

<style lang="scss">
.header {
  display: flex;
  flex-wrap: wrap;
  flex-direction: row;
  align-content: center;
  justify-content: flex-start;
  align-items: center;

  .title {
    margin-left: 25px;
    font-size: 25px;
  }

  .space {
    flex: 1;
  }
  height: 60px;

  :deep(.n-menu) {
    flex: auto 0 0;
    height: 60px;
    .n-menu-item {
      height: 60px;
    }
  }
}

header {
  display: flex;
  justify-content: center;
  margin-bottom: 8px;
  background-color: #041527;
  color: white;
}
</style>
