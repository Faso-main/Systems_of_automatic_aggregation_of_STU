// services/api.js
const API_BASE_URL = '';

// Утилиты для работы с localStorage
const getSessionId = () => localStorage.getItem('sessionId');
const saveSessionId = (sessionId) => localStorage.setItem('sessionId', sessionId);
const removeSessionId = () => localStorage.removeItem('sessionId');
const saveCurrentUser = (user) => localStorage.setItem('currentUser', JSON.stringify(user));
const getCurrentUser = () => {
  const userStr = localStorage.getItem('currentUser');
  return userStr ? JSON.parse(userStr) : null;
};
const removeCurrentUser = () => localStorage.removeItem('currentUser');

// Базовый запрос
async function apiRequest(endpoint, options = {}) {
  const url = `/api${endpoint}`;
  
  const config = {
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'application/json',
      ...options.headers,
    },
    credentials: 'include',
    ...options,
  };

  // Добавляем sessionId если есть
  const sessionId = getSessionId();
  if (sessionId) {
    config.headers['session-id'] = sessionId;
  }

  if (config.body && typeof config.body === 'object') {
    config.body = JSON.stringify(config.body);
  }

  try {
    console.log(`API Request: ${config.method || 'GET'} ${url}`, {
      headers: config.headers,
      body: config.body
    });

    const response = await fetch(url, config);
    
    // Проверяем Content-Type ответа
    const contentType = response.headers.get('content-type');
    let data;
    
    if (contentType && contentType.includes('application/json')) {
      data = await response.json();
    } else {
      const text = await response.text();
      throw new Error(`Неверный Content-Type ответа: ${contentType}. Ответ: ${text}`);
    }

    if (!response.ok) {
      throw new Error(data.error || `HTTP ${response.status}: ${response.statusText}`);
    }

    console.log(`API Response: ${response.status}`, data);
    return data;

  } catch (error) {
    console.error('API request error:', {
      url,
      error: error.message,
      stack: error.stack
    });
    throw error;
  }
}

// Auth API
export const authAPI = {
  async register(userData) {
    const response = await apiRequest('/auth/register', {
      method: 'POST',
      body: userData,
    });
    
    if (response.sessionId) {
      saveSessionId(response.sessionId);
    }
    
    if (response.user) {
      saveCurrentUser(response.user);
    }
    
    return response;
  },

  async login(credentials) {
    const response = await apiRequest('/auth/login', {
      method: 'POST',
      body: credentials,
    });
    
    if (response.sessionId) {
      saveSessionId(response.sessionId);
    }
    
    if (response.user) {
      saveCurrentUser(response.user);
    }
    
    return response;
  },

  async logout() {
    try {
      await apiRequest('/auth/logout', {
        method: 'POST',
      });
    } catch (error) {
      console.warn('Logout error (might be expected):', error.message);
    } finally {
      removeSessionId();
      removeCurrentUser();
    }
  },

  isAuthenticated() {
    return !!getSessionId();
  },

  getCurrentUser() {
    return getCurrentUser();
  }
};

// Products API
export const productsAPI = {
  async getProducts(filters = {}) {
    const queryString = new URLSearchParams(filters).toString();
    return apiRequest(`/products?${queryString}`);
  },

  async getProduct(id) {
    return apiRequest(`/products/${id}`);
  },

  async searchProducts(query) {
    return apiRequest(`/products/search?q=${encodeURIComponent(query)}`);
  }
};

// Procurements API
export const procurementsAPI = {
  async getProcurements(filters = {}) {
    const queryString = new URLSearchParams(filters).toString();
    return apiRequest(`/procurements?${queryString}`);
  },

  async getProcurement(id) {
    return apiRequest(`/procurements/${id}`);
  },

  async create(procurementData) {
    return apiRequest('/procurements', {
      method: 'POST',
      body: procurementData,
    });
  },

  async update(id, procurementData) {
    return apiRequest(`/procurements/${id}`, {
      method: 'PUT',
      body: procurementData,
    });
  },

  async delete(id) {
    return apiRequest(`/procurements/${id}`, {
      method: 'DELETE',
    });
  },

  async participate(procurementId, data) {
    return apiRequest(`/procurements/${procurementId}/participate`, {
      method: 'POST',
      body: data,
    });
  },

  async getParticipants(procurementId) {
    return apiRequest(`/procurements/${procurementId}/participants`);
  }
};

// User Profile API
export const userAPI = {
  async getProfile() {
    return apiRequest('/user/profile');
  },

  async updateProfile(userData) {
    const response = await apiRequest('/user/profile', {
      method: 'PUT',
      body: userData,
    });
    
    if (response.user) {
      saveCurrentUser(response.user);
    }
    
    return response;
  },

  async getMyProcurements() {
    return apiRequest('/user/my-procurements');
  },

  async getMyParticipations() {
    return apiRequest('/user/my-participations');
  },

  async changePassword(passwordData) {
    return apiRequest('/user/change-password', {
      method: 'POST',
      body: passwordData,
    });
  }
};

// Test connection
export const testAPI = {
  async health() {
    return apiRequest('/health');
  }
};