// modal/LoginForm.jsx
import { useState } from 'react';
import { authAPI } from '../services/api';
import './AuthForms.css';

function LoginForm({ onSwitchToRegister, onLoginSuccess }) {
  const [formData, setFormData] = useState({
    email: '',
    password: ''
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      const result = await authAPI.login({
        email: formData.email,
        password: formData.password
      });
      
      onLoginSuccess(result.user);
    } catch (error) {
      setError(error.message || 'Ошибка при входе. Проверьте email и пароль.');
    } finally {
      setLoading(false);
    }
  };

  const handleChange = (e) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value
    });
    setError('');
  };

  return (
    <form className="auth-form" onSubmit={handleSubmit}>
      {error && <div className="auth-error">{error}</div>}
      
      <div className="form-group">
        <label htmlFor="email">Email</label>
        <input
          type="email"
          id="email"
          name="email"
          value={formData.email}
          onChange={handleChange}
          placeholder="Введите ваш email"
          required
          disabled={loading}
        />
      </div>
      
      <div className="form-group">
        <label htmlFor="password">Пароль</label>
        <input
          type="password"
          id="password"
          name="password"
          value={formData.password}
          onChange={handleChange}
          placeholder="Введите ваш пароль"
          required
          disabled={loading}
        />
      </div>
      
      <button 
        type="submit" 
        className="btn-primary btn-full"
        disabled={loading}
      >
        {loading ? 'Вход...' : 'Войти'}
      </button>
      
      <div className="auth-switch">
        <p>Нет аккаунта? <button type="button" onClick={onSwitchToRegister}>Зарегистрироваться</button></p>
      </div>
    </form>
  );
}

export default LoginForm;