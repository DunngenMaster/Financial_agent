import axios from 'axios';

// Create axios instances for different backends
export const processAPI = axios.create({
  baseURL: 'http://localhost:8000',
  timeout: 300000, // 5 minutes
  headers: {
    'Accept': 'application/json',
  }
});

export const pathwayAPI = axios.create({
  baseURL: 'http://localhost:9000',
  timeout: 60000, // 1 minute
  headers: {
    'Accept': 'application/json',
  }
});