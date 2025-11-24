// components/ProductModal.jsx
import './ProductModal.css';

function ProductModal({ product, onClose, onAddToCart }) {
  if (!product) return null;

  return (
    <div className="product-modal">
      <div className="product-modal-content">
        <div className="product-modal-image">
          <img src={product.image} alt={product.name} />
        </div>
        
        <div className="product-modal-info">
          <h2>{product.name}</h2>
          <p className="product-price">{product.price} ₽</p>
          <p className="product-description">{product.description}</p>
          
          <div className="product-details">
            <div className="detail-item">
              <span className="detail-label">Категория:</span>
              <span className="detail-value">{product.category}</span>
            </div>
            <div className="detail-item">
              <span className="detail-label">Бренд:</span>
              <span className="detail-value">{product.brand}</span>
            </div>
            <div className="detail-item">
              <span className="detail-label">В наличии:</span>
              <span className="detail-value">{product.stock} шт.</span>
            </div>
          </div>
          
          <div className="product-actions">
            <button className="btn-primary" onClick={onAddToCart}>
              Добавить в корзину
            </button>
            <button className="btn-secondary" onClick={onClose}>
              Продолжить покупки
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default ProductModal;