<template>
  <!-- Thumb-reachable action bar pinned above the tab bar (phone) or the bottom edge (rail layouts). -->
  <div
    class="pointer-events-none fixed inset-x-0 z-40 px-3 md:left-[84px] md:px-6"
    :style="{ bottom: 'calc(var(--tabbar-h, 0px) + env(safe-area-inset-bottom))' }"
  >
    <div class="pointer-events-auto mx-auto mb-2.5 max-w-3xl rounded-3xl bg-elevated/95 p-2.5 shadow-pop ring-1 ring-inset ring-line backdrop-blur-md md:mb-4">
      <slot />
    </div>
  </div>
</template>
