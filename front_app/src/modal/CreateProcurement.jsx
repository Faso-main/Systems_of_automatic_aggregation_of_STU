// modal/CreateProcurement.jsx
import { useState } from 'react';
import './CreateProcurement.css';

function CreateProcurement({ onClose, onCreate }) {
  const [formData, setFormData] = useState({
    title: '',
    description: '',
    session_number: '',
    customer_name: '',
    customer_inn: '',
    current_price: '',
    start_date: '',
    end_date: '',
    law_type: '44-ФЗ',
    contract_terms: '',
    contract_security: ''
  });
  const [products, setProducts] = useState([{ product_id: '', required_quantity: 1, max_price: '' }]);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);

    try {
      // Валидация
      if (!formData.title || !formData.session_number || !formData.current_price) {
        alert('Заполните обязательные поля: название, номер сессии и начальная цена');
        return;
      }

      const procurementData = {
        ...formData,
        current_price: parseFloat(formData.current_price),
        products: products.filter(p => p.product_id && p.required_quantity > 0)
      };

      await onCreate(procurementData);
      alert('Закупка успешно создана!');
      onClose();
    } catch (error) {
      alert('Ошибка при создании закупки: ' + error.message);
    } finally {
      setLoading(false);
    }
  };

  const handleChange = (e) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value
    });
  };

  const addProduct = () => {
    setProducts([...products, { product_id: '', required_quantity: 1, max_price: '' }]);
  };

  const removeProduct = (index) => {
    if (products.length > 1) {
      setProducts(products.filter((_, i) => i !== index));
    }
  };

  const updateProduct = (index, field, value) => {
    const updatedProducts = [...products];
    updatedProducts[index][field] = value;
    setProducts(updatedProducts);
  };

  return (
    <div className="create-procurement">      
      <form onSubmit={handleSubmit}>
        <div className="form-section">
          
          <div className="form-row">
            <div className="form-group">
              <label htmlFor="title">Название закупки *</label>
              <input
                type="text"
                id="title"
                name="title"
                value={formData.title}
                onChange={handleChange}
                required
                placeholder="Например: Поставка офисной техники"
              />
            </div>
            
            <div className="form-group">
              <label htmlFor="session_number">Номер котировочной сессии *</label>
              <input
                type="text"
                id="session_number"
                name="session_number"
                value={formData.session_number}
                onChange={handleChange}
                required
                placeholder="Например: 10055209"
              />
            </div>
          </div>

          <div className="form-row">
            <div className="form-group">
              <label htmlFor="current_price">Начальная цена, ₽ *</label>
              <input
                type="number"
                id="current_price"
                name="current_price"
                value={formData.current_price}
                onChange={handleChange}
                required
                min="0"
                step="0.01"
                placeholder="0.00"
              />
            </div>
            
            <div className="form-group">
              <label htmlFor="law_type">Тип закупки</label>
              <select
                id="law_type"
                name="law_type"
                value={formData.law_type}
                onChange={handleChange}
              >
                <option value="44-ФЗ">44-ФЗ</option>
                <option value="223-ФЗ">223-ФЗ</option>
                <option value="Коммерческая">Коммерческая</option>
              </select>
            </div>
          </div>

          <div className="form-group">
            <label htmlFor="description">Описание закупки</label>
            <textarea
              id="description"
              name="description"
              value={formData.description}
              onChange={handleChange}
              rows="3"
              placeholder="Подробное описание требований и условий закупки..."
            />
          </div>
        </div>

        <div className="form-section">
          <h4>Сроки проведения</h4>
          
          <div className="form-row">
            <div className="form-group">
              <label htmlFor="start_date">Дата начала *</label>
              <input
                type="datetime-local"
                id="start_date"
                name="start_date"
                value={formData.start_date}
                onChange={handleChange}
                required
              />
            </div>
            
            <div className="form-group">
              <label htmlFor="end_date">Дата окончания *</label>
              <input
                type="datetime-local"
                id="end_date"
                name="end_date"
                value={formData.end_date}
                onChange={handleChange}
                required
              />
            </div>
          </div>
        </div>

        <div className="form-section">
          <div className="section-header">
            <h4>Товары в закупке</h4>
            <button type="button" className="btn-outline" onClick={addProduct}>
              + Добавить товар
            </button>
          </div>
          
          {products.map((product, index) => (
            <div key={index} className="product-row">
              <div className="form-row">
                <div className="form-group">
                  <label>Товар</label>
                  <input
                    type="text"
                    placeholder="ID товара или наименование"
                    value={product.product_id}
                    onChange={(e) => updateProduct(index, 'product_id', e.target.value)}
                  />
                </div>
                
                <div className="form-group">
                  <label>Количество</label>
                  <input
                    type="number"
                    min="1"
                    value={product.required_quantity}
                    onChange={(e) => updateProduct(index, 'required_quantity', parseInt(e.target.value) || 1)}
                  />
                </div>
                
                <div className="form-group">
                  <label>&nbsp;</label>
                  <button 
                    type="button" 
                    className="btn-remove"
                    onClick={() => removeProduct(index)}
                    disabled={products.length === 1}
                  >
                    ×
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>

        <div className="form-actions">
          <button type="button" className="btn-outline" onClick={onClose}>
            Отмена
          </button>
          <button type="submit" className="btn-primary" disabled={loading}>
            {loading ? 'Создание...' : 'Создать закупку'}
          </button>
        </div>
      </form>
    </div>
  );
}

export default CreateProcurement;