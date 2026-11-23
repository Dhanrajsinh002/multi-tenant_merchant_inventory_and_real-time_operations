import axios from 'axios'

const api = axios.create({
    baseURL: '',
    headers: {
        'Content-Type': 'application/json',
    },
})

// Attach JWT token to request automatically
api.interceptors.request.use((config) => {
    const token = localStorage.getItem('cleandesk_token')
    if (token) {
        config.headers.Authorization = `Bearer ${token}`
    }
    return config
})

// Client error response interceptor
api.interceptors.response.use(
    (response) => response,
    (error) => {
        const errorData = error.response?.data
        if (errorData?.detail) {
            return Promise.reject(errorData.detail)
        }
        return Promise.reject({
            error_code: 'NETWORK_ERROR',
            message: error.message || 'Netowrk request failed',
        })
    }
)

export default api
