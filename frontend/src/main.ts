import { createApp } from 'vue';
import { createPinia } from 'pinia';
import { setConfig, frappeRequest, resourcesPlugin } from 'frappe-ui';
import router from './router';
import App from './App.vue';
import './index.css';

// Configure frappe-ui to use the standard request helper
setConfig('resourceFetcher', frappeRequest);

const app = createApp(App);

app.use(createPinia());
app.use(resourcesPlugin);
app.use(router);

app.mount('#app');
