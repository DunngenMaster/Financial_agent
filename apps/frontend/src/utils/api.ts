import axios from 'axios';

// Configure global axios defaults
axios.defaults.withCredentials = true;
axios.defaults.headers.common['Accept'] = 'application/json';
axios.defaults.timeout = 60000;

// Export configured axios instances
export const api = {
  process: axios.create({
    baseURL: 'http://localhost:8000',
  }),
  
  pathway: axios.create({
    baseURL: 'http://localhost:9000',
  })
};

// Add response interceptor to log responses
axios.interceptors.response.use(
  response => {
    console.log(`[API] ${response.config.method?.toUpperCase()} ${response.config.url} - ${response.status}`);
    return response;
  },
  error => {
    console.error('[API Error]', error);
    return Promise.reject(error);
  }
);