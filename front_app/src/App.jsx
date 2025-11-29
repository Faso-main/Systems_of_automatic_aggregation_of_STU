import React, { useMemo, useState } from "react";

const initialCategories = [
  {
    id: 101,
    name: "Валенки классические",
    description:
      "Тёплые валенки для зимы. Натуральная шерсть, высота до середины голени.",
    createdAt: "2025-11-24",
    status: "approved",
    rating: 4,
    colors: ["серый", "чёрный", "бежевый"],
    sizes: ["35", "36", "37", "38", "39", "40", "41"]
  },
  {
    id: 102,
    name: "Галоши утеплённые",
    description: "Утеплённые галоши для города и дачи. Влагоустойчивая подошва.",
    createdAt: "2025-11-28",
    status: "approved",
    rating: 5,
    colors: ["чёрный", "хаки"],
    sizes: ["36", "37", "38", "39", "40", "41", "42"]
  },
  {
    id: 103,
    name: "Домашние тапочки",
    description:
      "Лёгкие тапочки для дома, мягкая подошва, нескользящее основание.",
    createdAt: "2025-11-15",
    status: "rejected",
    rating: 3,
    colors: ["синий", "бордовый"],
    sizes: ["36", "37", "38", "39", "40"]
  }
];

const formatDate = (iso) => new Date(iso).toLocaleDateString("ru-RU");

function App() {
  const [categories, setCategories] = useState(initialCategories);
  const [selectedCategoryId, setSelectedCategoryId] = useState(
    initialCategories[0]?.id ?? null
  );

  const [search, setSearch] = useState("");
  const [filterId, setFilterId] = useState("");
  const [filterStatus, setFilterStatus] = useState("all");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");

  const selectedCategory = useMemo(
    () => categories.find((c) => c.id === selectedCategoryId) ?? null,
    [categories, selectedCategoryId]
  );

  const filteredCategories = useMemo(
    () =>
      categories.filter((cat) => {
        if (
          search &&
          !`${cat.name} ${cat.description}`
            .toLowerCase()
            .includes(search.toLowerCase())
        ) {
          return false;
        }
        if (filterId && !String(cat.id).includes(filterId.trim())) return false;
        if (filterStatus !== "all" && cat.status !== filterStatus) return false;
        if (dateFrom && new Date(cat.createdAt) < new Date(dateFrom))
          return false;
        if (dateTo && new Date(cat.createdAt) > new Date(dateTo)) return false;
        return true;
      }),
    [categories, search, filterId, filterStatus, dateFrom, dateTo]
  );

  const handleRegenerate = (id) => {
    console.log("Перегенерировать категорию", id);
    alert(`Перегенерация категории ID ${id} (заглушка)`);
  };

  const handleRatingChange = (id, rating) => {
    setCategories((prev) =>
      prev.map((c) => (c.id === id ? { ...c, rating } : c))
    );
  };

  return (
    <div className="app-root">
      <header className="header">
        <div className="header-left">
          <div className="logo">
            <span className="logo-main">Портал поставщиков</span>
            <span className="logo-sub">Управление категориями товаров</span>
          </div>
        </div>
        <div className="header-right">
          <div className="user-info">
            <span className="user-label">Личный кабинет</span>
            <span className="user-name">IVANOV A.</span>
          </div>
          <div className="user-avatar">IA</div>
        </div>
      </header>

      <div className="toolbar">
        <div className="toolbar-left">
          <div className="toolbar-title">Категории товаров</div>
        </div>
      </div>

      <main className="layout">
        <section className="panel-left">
          <div className="filters-block">
            <div className="filters-header">Фильтры</div>
            <div className="filters-row">
              <div className="filter-item wide">
                <label>Поиск по названию или описанию</label>
                <input
                  className="input"
                  placeholder="Введите текст..."
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                />
              </div>
            </div>
            <div className="filters-row">
              <div className="filter-item">
                <label>ID категории</label>
                <input
                  className="input"
                  placeholder="Например, 101"
                  value={filterId}
                  onChange={(e) => setFilterId(e.target.value)}
                />
              </div>
              <div className="filter-item">
                <label>Статус одобрения</label>
                <select
                  className="input"
                  value={filterStatus}
                  onChange={(e) => setFilterStatus(e.target.value)}
                >
                  <option value="all">Все</option>
                  <option value="approved">Одобрено</option>
                  <option value="rejected">Не одобрено</option>
                </select>
              </div>
              <div className="filter-item">
                <label>Дата с</label>
                <input
                  type="date"
                  className="input"
                  value={dateFrom}
                  onChange={(e) => setDateFrom(e.target.value)}
                />
              </div>
              <div className="filter-item">
                <label>Дата по</label>
                <input
                  type="date"
                  className="input"
                  value={dateTo}
                  onChange={(e) => setDateTo(e.target.value)}
                />
              </div>
            </div>
          </div>

          <div className="table-wrapper">
            <table className="table">
              <thead>
                <tr>
                  <th>ID категории</th>
                  <th>Название категории</th>
                  <th>Описание</th>
                  <th>Дата создания</th>
                  <th>Статус</th>
                  <th>Оценка</th>
                  <th>Действия</th>
                </tr>
              </thead>
              <tbody>
                {filteredCategories.length === 0 && (
                  <tr>
                    <td className="table-empty" colSpan={7}>
                      Нет категорий, подходящих под фильтр
                    </td>
                  </tr>
                )}
                {filteredCategories.map((cat) => (
                  <tr
                    key={cat.id}
                    className={
                      cat.id === selectedCategoryId ? "row-selected" : ""
                    }
                    onClick={() => setSelectedCategoryId(cat.id)}
                  >
                    <td>{cat.id}</td>
                    <td className="cell-link">{cat.name}</td>
                    <td className="cell-desc">{cat.description}</td>
                    <td>{formatDate(cat.createdAt)}</td>
                    <td>
                      {cat.status === "approved" ? (
                        <span className="badge badge-success">Да</span>
                      ) : (
                        <span className="badge badge-danger">Нет</span>
                      )}
                    </td>
                    <td>
                      <StarRating
                        value={cat.rating}
                        onChange={(r) => handleRatingChange(cat.id, r)}
                      />
                    </td>
                    <td>
                      <button
                        className="btn btn-sm"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleRegenerate(cat.id);
                        }}
                      >
                        Перегенерировать
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <section className="panel-right">
          {!selectedCategory ? (
            <div className="empty-card">Выберите категорию в таблице слева</div>
          ) : (
            <CategoryCard
              category={selectedCategory}
              onRegenerate={() => handleRegenerate(selectedCategory.id)}
              onRatingChange={(r) =>
                handleRatingChange(selectedCategory.id, r)
              }
            />
          )}
        </section>
      </main>
    </div>
  );
}

function StarRating({ value, onChange }) {
  const handleClick = (v) => {
    if (onChange) onChange(v);
  };

  return (
    <div className="stars">
      {[1, 2, 3, 4, 5].map((v) => (
        <span
          key={v}
          className={
            "star " +
            (v <= value ? "star-filled " : "") +
            (onChange ? "star-clickable" : "")
          }
          onClick={() => handleClick(v)}
        >
          ★
        </span>
      ))}
      <span className="stars-value">{value.toFixed(1)}</span>
    </div>
  );
}

function CategoryCard({ category, onRegenerate, onRatingChange }) {
  const [selectedColor, setSelectedColor] = useState(category.colors[0]);
  const [selectedSize, setSelectedSize] = useState(category.sizes[0]);

  return (
    <div className="card">
      <div className="card-header">
        <div>
          <h2>{category.name}</h2>
          <div className="card-subtitle">
            ID категории: {category.id} · Создано: {formatDate(category.createdAt)}
          </div>
        </div>
        <div className="card-status-group">
          <span className="card-status-label">Статус:</span>
          {category.status === "approved" ? (
            <span className="badge badge-success">Одобрено администратором</span>
          ) : (
            <span className="badge badge-danger">
              Не одобрено администратором
            </span>
          )}
        </div>
      </div>

      <div className="card-body">
        <div className="card-image-block">
          <div className="image-placeholder">
            <span>Превью категории</span>
          </div>
        </div>

        <div className="card-info">
          <div className="card-rating-row">
            <span>Оценка агрегации:</span>
            <StarRating value={category.rating} onChange={onRatingChange} />
          </div>

          <div className="card-section">
            <h3>Описание</h3>
            <p>{category.description}</p>
          </div>

          <div className="card-section">
            <h3>Вариации товара</h3>

            <div className="card-variants">
              <div className="variant-block">
                <div className="variant-label">Цвет</div>
                <div className="variant-options">
                  {category.colors.map((color) => (
                    <button
                      key={color}
                      className={
                        "chip " +
                        (color === selectedColor ? "chip-selected" : "")
                      }
                      onClick={() => setSelectedColor(color)}
                    >
                      {color}
                    </button>
                  ))}
                </div>
              </div>

              <div className="variant-block">
                <div className="variant-label">Размер (RU)</div>
                <div className="variant-options">
                  {category.sizes.map((size) => (
                    <button
                      key={size}
                      className={
                        "chip " +
                        (size === selectedSize ? "chip-selected" : "")
                      }
                      onClick={() => setSelectedSize(size)}
                    >
                      {size}
                    </button>
                  ))}
                </div>
              </div>

              <div className="variant-summary">
                Текущая вариация: <b>{selectedColor}</b>, размер{" "}
                <b>{selectedSize}</b>
              </div>
            </div>
          </div>

          <div className="card-actions">
            <button className="btn" onClick={onRegenerate}>
              Перегенерировать
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;
