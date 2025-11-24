## 1. Создаем базу данных и пользователей

```sql
-- Подключаемся как суперпользователь
psql -U postgres

-- Создаем базу данных
CREATE DATABASE online_store1 
    ENCODING = 'UTF8'
    LC_COLLATE = 'C'
    LC_CTYPE = 'C'
    TEMPLATE = template0;

-- Подключаемся к новой базе
\c online_store1

-- Создаем пользователей
CREATE USER store_app1 WITH PASSWORD '1234';
CREATE USER store_reader1 WITH PASSWORD '1234';

-- Создаем схему
CREATE SCHEMA store;
SET search_path TO store, public;
```

## 2. Создаем таблицы

```sql
-- Таблица пользователей
CREATE TABLE store.users (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    INN VARCHAR(12) NOT NULL,
    company_name VARCHAR(500),
    location VARCHAR(500),
    phone_number VARCHAR(50),
    role VARCHAR(50) DEFAULT 'customer',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Таблица категорий (по вашему дереву)
CREATE TABLE store.categories (
    id INTEGER PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    parent_id INTEGER NULL,
    level INTEGER NOT NULL,
    description TEXT,
    sort_order INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (parent_id) REFERENCES store.categories(id) ON DELETE SET NULL
);

-- Таблица товаров
CREATE TABLE store.products (
    id SERIAL PRIMARY KEY,
    name VARCHAR(500) NOT NULL,
    category_id INTEGER NOT NULL,
    company VARCHAR(255),
    price_per_item DECIMAL(12,2) NOT NULL CHECK (price_per_item >= 0),
    amount INTEGER NOT NULL DEFAULT 0 CHECK (amount >= 0),
    manufacturer VARCHAR(255),
    location VARCHAR(500),
    description TEXT,
    specifications JSONB,
    sku VARCHAR(100) UNIQUE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (category_id) REFERENCES store.categories(id) ON DELETE RESTRICT
);

-- Таблица закупок
CREATE TABLE store.procurements (
    id SERIAL PRIMARY KEY,
    session_number VARCHAR(100) UNIQUE NOT NULL, -- Котировочная сессия
    title VARCHAR(1000) NOT NULL, -- Название закупки
    status VARCHAR(50) DEFAULT 'active', -- active, soon, completed
    current_price DECIMAL(12,2) NOT NULL,
    description TEXT, -- Описание закупки
    contract_terms TEXT, -- Условия исполнения контракта
    contract_security TEXT, -- Обеспечение исполнения контракта
    customer_name VARCHAR(500) NOT NULL, -- Заказчик
    customer_inn VARCHAR(12), -- ИНН заказчика
    law_type VARCHAR(100), -- 44-ФЗ, 223-ФЗ и т.д.
    start_date TIMESTAMP NOT NULL,
    end_date TIMESTAMP NOT NULL,
    created_by INTEGER, -- Кто создал закупку
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (created_by) REFERENCES store.users(id) ON DELETE SET NULL
);

-- Таблица товаров в закупках (связь многие-ко-многим)
CREATE TABLE store.procurement_products (
    id SERIAL PRIMARY KEY,
    procurement_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    required_quantity INTEGER NOT NULL CHECK (required_quantity > 0),
    max_price DECIMAL(12,2), -- Максимальная цена за единицу
    specifications JSONB, -- Дополнительные требования
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (procurement_id) REFERENCES store.procurements(id) ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES store.products(id) ON DELETE RESTRICT,
    UNIQUE(procurement_id, product_id)
);

-- Таблица участников закупок
CREATE TABLE store.procurement_participants (
    id SERIAL PRIMARY KEY,
    procurement_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    proposed_price DECIMAL(12,2), -- Предложенная цена
    proposal_text TEXT, -- Текст предложения
    status VARCHAR(50) DEFAULT 'pending', -- pending, approved, rejected
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (procurement_id) REFERENCES store.procurements(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES store.users(id) ON DELETE CASCADE,
    UNIQUE(procurement_id, user_id)
);
```

## 3. Создаем индексы

```sql
-- Индексы для пользователей
CREATE INDEX idx_users_email ON store.users(email);
CREATE INDEX idx_users_inn ON store.users(INN);
CREATE INDEX idx_users_company ON store.users(company_name);
CREATE INDEX idx_users_active ON store.users(is_active) WHERE is_active = true;

-- Индексы для категорий
CREATE INDEX idx_categories_parent_id ON store.categories(parent_id);
CREATE INDEX idx_categories_level ON store.categories(level);
CREATE INDEX idx_categories_active ON store.categories(is_active);

-- Индексы для товаров
CREATE INDEX idx_products_category_id ON store.products(category_id);
CREATE INDEX idx_products_company ON store.products(company);
CREATE INDEX idx_products_price ON store.products(price_per_item);
CREATE INDEX idx_products_active ON store.products(is_active);
CREATE INDEX idx_products_sku ON store.products(sku);

-- Индексы для закупок
CREATE INDEX idx_procurements_status ON store.procurements(status);
CREATE INDEX idx_procurements_dates ON store.procurements(start_date, end_date);
CREATE INDEX idx_procurements_customer ON store.procurements(customer_name);
CREATE INDEX idx_procurements_session ON store.procurements(session_number);
CREATE INDEX idx_procurements_active ON store.procurements(is_active) WHERE is_active = true;

-- Индексы для связующих таблиц
CREATE INDEX idx_procurement_products_procurement ON store.procurement_products(procurement_id);
CREATE INDEX idx_procurement_products_product ON store.procurement_products(product_id);
CREATE INDEX idx_procurement_participants_procurement ON store.procurement_participants(procurement_id);
CREATE INDEX idx_procurement_participants_user ON store.procurement_participants(user_id);
CREATE INDEX idx_procurement_participants_status ON store.procurement_participants(status);
```

## 4. Создаем триггеры для updated_at

```sql
-- Функция для обновления updated_at
CREATE OR REPLACE FUNCTION store.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Триггеры для таблиц с updated_at
CREATE TRIGGER update_users_updated_at 
    BEFORE UPDATE ON store.users 
    FOR EACH ROW EXECUTE FUNCTION store.update_updated_at_column();

CREATE TRIGGER update_products_updated_at 
    BEFORE UPDATE ON store.products 
    FOR EACH ROW EXECUTE FUNCTION store.update_updated_at_column();

CREATE TRIGGER update_procurements_updated_at 
    BEFORE UPDATE ON store.procurements 
    FOR EACH ROW EXECUTE FUNCTION store.update_updated_at_column();

CREATE TRIGGER update_procurement_participants_updated_at 
    BEFORE UPDATE ON store.procurement_participants 
    FOR EACH ROW EXECUTE FUNCTION store.update_updated_at_column();
```

## 5. Наполняем категории по вашему дереву

```sql
-- Вставляем категории уровня 1
INSERT INTO store.categories (id, name, parent_id, level, description, sort_order) VALUES
(1, 'Электроника', NULL, 1, 'Электронные устройства и гаджеты', 1),
(2, 'Бытовая техника', NULL, 1, 'Техника для дома', 2),
(3, 'Одежда', NULL, 1, 'Одежда и аксессуары', 3),
(4, 'Мебель', NULL, 1, 'Мебель для дома и офиса', 4);

-- Вставляем категории уровня 2
INSERT INTO store.categories (id, name, parent_id, level, description, sort_order) VALUES
(100, 'Смартфоны и гаджеты', 1, 2, 'Мобильные устройства и гаджеты', 1),
(101, 'Компьютерная техника', 1, 2, 'Компьютеры и комплектующие', 2),
(102, 'Бытовая электроника', 1, 2, 'Электроника для дома', 3),
(200, 'Крупная техника', 2, 2, 'Крупная бытовая техника', 1),
(201, 'Кухонная техника', 2, 2, 'Техника для кухни', 2),
(202, 'Климатическая техника', 2, 2, 'Техника для климат-контроля', 3),
(300, 'Мужская', 3, 2, 'Одежда для мужчин', 1),
(301, 'Женская', 3, 2, 'Одежда для женщин', 2),
(302, 'Детская', 3, 2, 'Одежда для детей', 3),
(400, 'Для гостиной', 4, 2, 'Мебель для гостиной', 1),
(401, 'Для спальни', 4, 2, 'Мебель для спальни', 2),
(402, 'Для кухни', 4, 2, 'Мебель для кухни', 3);

-- Вставляем категории уровня 3
INSERT INTO store.categories (id, name, parent_id, level, description, sort_order) VALUES
-- Электроника -> Смартфоны и гаджеты
(10000, 'Смартфоны', 100, 3, 'Мобильные телефоны', 1),
(10001, 'Планшеты', 100, 3, 'Планшеты и iPad', 2),
(10002, 'Умные часы', 100, 3, 'Смарт-часы', 3),
(10003, 'Фитнес-браслеты', 100, 3, 'Фитнес-трекеры', 4),

-- Электроника -> Компьютерная техника
(10100, 'Ноутбуки', 101, 3, 'Портативные компьютеры', 1),
(10101, 'Системные блоки', 101, 3, 'Стационарные компьютеры', 2),
(10102, 'Мониторы', 101, 3, 'Компьютерные мониторы', 3),
(10103, 'Периферия', 101, 3, 'Компьютерная периферия', 4),

-- Электроника -> Бытовая электроника
(10200, 'Телевизоры', 102, 3, 'Телевизоры и Smart TV', 1),
(10201, 'Аудиотехника', 102, 3, 'Аудиосистемы и колонки', 2),
(10202, 'Фототехника', 102, 3, 'Фотоаппараты и объективы', 3),
(10203, 'Игровые консоли', 102, 3, 'Игровые приставки', 4),

-- Бытовая техника -> Крупная техника
(20000, 'Холодильники', 200, 3, 'Холодильные установки', 1),
(20001, 'Стиральные машины', 200, 3, 'Стиральные машины', 2),
(20002, 'Плиты', 200, 3, 'Кухонные плиты', 3),
(20003, 'Посудомойки', 200, 3, 'Посудомоечные машины', 4),

-- Бытовая техника -> Кухонная техника
(20100, 'Микроволновки', 201, 3, 'Микроволновые печи', 1),
(20101, 'Кофеварки', 201, 3, 'Кофемашины и кофеварки', 2),
(20102, 'Блендеры', 201, 3, 'Блендеры и миксеры', 3),
(20103, 'Мультиварки', 201, 3, 'Мультиварки и скороварки', 4),

-- Бытовая техника -> Климатическая техника
(20200, 'Кондиционеры', 202, 3, 'Кондиционеры и сплит-системы', 1),
(20201, 'Обогреватели', 202, 3, 'Обогреватели', 2),
(20202, 'Вентиляторы', 202, 3, 'Вентиляторы', 3),
(20203, 'Увлажнители', 202, 3, 'Увлажнители воздуха', 4),

-- Одежда -> Мужская
(30000, 'Верхняя одежда', 300, 3, 'Куртки, пальто', 1),
(30001, 'Футболки и рубашки', 300, 3, 'Футболки, рубашки', 2),
(30002, 'Брюки и джинсы', 300, 3, 'Брюки, джинсы', 3),
(30003, 'Обувь', 300, 3, 'Мужская обувь', 4),

-- Одежда -> Женская
(30100, 'Платья и юбки', 301, 3, 'Платья, юбки', 1),
(30101, 'Блузки и топы', 301, 3, 'Блузки, топы', 2),
(30102, 'Брюки', 301, 3, 'Женские брюки', 3),
(30103, 'Обувь', 301, 3, 'Женская обувь', 4),

-- Одежда -> Детская
(30200, 'Для мальчиков', 302, 3, 'Одежда для мальчиков', 1),
(30201, 'Для девочек', 302, 3, 'Одежда для девочек', 2),
(30202, 'Обувь', 302, 3, 'Детская обувь', 3),
(30203, 'Школьная форма', 302, 3, 'Школьная форма', 4),

-- Мебель -> Для гостиной
(40000, 'Диваны и кресла', 400, 3, 'Мягкая мебель', 1),
(40001, 'Столы', 400, 3, 'Журнальные и кофейные столы', 2),
(40002, 'Стенки', 400, 3, 'Гостиные стенки', 3),
(40003, 'Стулья', 400, 3, 'Стулья для гостиной', 4),

-- Мебель -> Для спальни
(40100, 'Кровати', 401, 3, 'Кровати и спальные гарнитуры', 1),
(40101, 'Шкафы', 401, 3, 'Гардеробные шкафы', 2),
(40102, 'Тумбы', 401, 3, 'Прикроватные тумбы', 3),
(40103, 'Матрасы', 401, 3, 'Матрасы', 4),

-- Мебель -> Для кухни
(40200, 'Кухонные гарнитуры', 402, 3, 'Кухонные гарнитуры', 1),
(40201, 'Обеденные группы', 402, 3, 'Обеденные столы и стулья', 2),
(40202, 'Стулья', 402, 3, 'Кухонные стулья', 3),
(40203, 'Бары', 402, 3, 'Барные стойки', 4);
```

## 6. Настраиваем права доступа

```sql
-- Даем права на подключение к базе
GRANT CONNECT ON DATABASE online_store1 TO store_app1, store_reader1;

-- Даем права на использование схемы
GRANT USAGE ON SCHEMA store TO store_app1, store_reader1;

-- Права для приложения (полный доступ к данным)
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA store TO store_app1;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA store TO store_app1;

-- Права для чтения
GRANT SELECT ON ALL TABLES IN SCHEMA store TO store_reader1;
GRANT SELECT ON ALL SEQUENCES IN SCHEMA store TO store_reader1;

-- Права по умолчанию для будущих таблиц
ALTER DEFAULT PRIVILEGES IN SCHEMA store 
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO store_app1;

ALTER DEFAULT PRIVILEGES IN SCHEMA store 
    GRANT SELECT ON TABLES TO store_reader1;
```

## 7. Проверяем структуру

```sql
-- Проверяем количество категорий по уровням
SELECT level, COUNT(*) as category_count 
FROM store.categories 
GROUP BY level 
ORDER BY level;

-- Проверяем дерево категорий
WITH RECURSIVE category_tree AS (
    SELECT 
        id, 
        name, 
        parent_id,
        level,
        name as full_path
    FROM store.categories 
    WHERE parent_id IS NULL
    
    UNION ALL
    
    SELECT 
        c.id, 
        c.name, 
        c.parent_id,
        c.level,
        ct.full_path || ' → ' || c.name
    FROM store.categories c
    INNER JOIN category_tree ct ON c.parent_id = ct.id
)
SELECT id, level, full_path 
FROM category_tree 
ORDER BY full_path;

-- Проверяем таблицы
SELECT 
    table_name,
    (SELECT COUNT(*) FROM store.users) as users_count,
    (SELECT COUNT(*) FROM store.categories) as categories_count,
    (SELECT COUNT(*) FROM store.products) as products_count,
    (SELECT COUNT(*) FROM store.procurements) as procurements_count;
```

## 8. Простой сервер для проверки

### package.json
```json
{
  "name": "online-store1-backend",
  "version": "1.0.0",
  "type": "module",
  "scripts": {
    "dev": "nodemon server.js",
    "start": "node server.js"
  },
  "dependencies": {
    "express": "^4.18.2",
    "cors": "^2.8.5",
    "bcryptjs": "^2.4.3",
    "pg": "^8.11.3"
  },
  "devDependencies": {
    "nodemon": "^3.0.1"
  }
}
```

### server.js
```javascript
import express from 'express';
import cors from 'cors';
import pkg from 'pg';

const { Pool } = pkg;
const app = express();
const PORT = 5000;

// Middleware
app.use(cors());
app.use(express.json());

// PostgreSQL connection
const pool = new Pool({
  user: 'store_app1',
  host: 'localhost',
  database: 'online_store1',
  password: '1234',
  port: 5432,
});

// Health check
app.get('/api/health', async (req, res) => {
  try {
    const result = await pool.query('SELECT NOW() as time');
    res.json({ 
      status: 'OK', 
      database: 'online_store1',
      time: result.rows[0].time 
    });
  } catch (error) {
    res.status(500).json({ error: 'Database connection error' });
  }
});

// Get categories tree
app.get('/api/categories', async (req, res) => {
  try {
    const result = await pool.query(`
      SELECT id, name, parent_id, level, description
      FROM store.categories 
      WHERE is_active = true
      ORDER BY level, parent_id NULLS FIRST, sort_order
    `);
    
    res.json({ categories: result.rows });
  } catch (error) {
    console.error('Categories error:', error);
    res.status(500).json({ error: 'Error fetching categories' });
  }
});

app.listen(PORT, () => {
  console.log(`Сервер запущен на порту ${PORT}`);
  console.log(`База данных: online_store1`);
  console.log(`Пользователь БД: store_app1`);
  console.log(`Проверка: http://localhost:${PORT}/api/health`);
});
```
