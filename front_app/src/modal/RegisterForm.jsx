// modal/RegisterForm.jsx
import { useState } from 'react';
import { authAPI } from '../services/api';
import './AuthForms.css';

function RegisterForm({ onSwitchToLogin, onRegisterSuccess }) {
  const [formData, setFormData] = useState({
    name: '',
    email: '',
    password: '',
    INN: '',
    company_name: '',
    phone_number: ''
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      const result = await authAPI.register(formData);
      onRegisterSuccess(result.user);
    } catch (error) {
      setError(error.message || 'Ошибка при регистрации. Попробуйте еще раз.');
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
        <label htmlFor="name">Имя *</label>
        <input
          type="text"
          id="name"
          name="name"
          value={formData.name}
          onChange={handleChange}
          placeholder="Введите ваше имя"
          required
          disabled={loading}
        />
      </div>
      
      <div className="form-group">
        <label htmlFor="email">Email *</label>
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
        <label htmlFor="password">Пароль *</label>
        <input
          type="password"
          id="password"
          name="password"
          value={formData.password}
          onChange={handleChange}
          placeholder="Придумайте пароль"
          required
          disabled={loading}
        />
      </div>

      <div className="form-group">
        <label htmlFor="INN">ИНН *</label>
        <input
          type="text"
          id="INN"
          name="INN"
          value={formData.INN}
          onChange={handleChange}
          placeholder="123456789456"
          required
          disabled={loading}
          maxLength="12"
          pattern="[0-9]{10,12}"
        />
      </div>

      <div className="form-group">
        <label htmlFor="company_name">Название компании</label>
        <input
          type="text"
          id="company_name"
          name="company_name"
          value={formData.company_name}
          onChange={handleChange}
          placeholder="Название вашей компании"
          disabled={loading}
        />
      </div>

      <div className="form-group">
        <label htmlFor="phone_number">Телефон</label>
        <input
          type="tel"
          id="phone_number"
          name="phone_number"
          value={formData.phone_number}
          onChange={handleChange}
          placeholder="+7 (999) 999-99-99"
          disabled={loading}
        />
      </div>
      
      <button 
        type="submit" 
        className="btn-primary btn-full"
        disabled={loading}
      >
        {loading ? 'Регистрация...' : 'Зарегистрироваться'}
      </button>
      
      <div className="auth-switch">
        <p>Уже есть аккаунт? <button type="button" onClick={onSwitchToLogin}>Войти</button></p>
      </div>
    </form>
  );
}

export default RegisterForm;