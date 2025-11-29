// src/App.jsx
import React, { useMemo, useState, useEffect } from "react";
import "./styles.css";

const API_BASE = "http://localhost:5000";

const formatDate = (iso) =>
  iso ? new Date(iso).toLocaleDateString("ru-RU") : "—";

function App() {
  const [categories, setCategories] = useState([]);
  const [selectedCategoryId, setSelectedCategoryId] = useState(null);

  const [search, setSearch] = useState("");
  const [filterId, setFilterId] = useState("");
  const [filterStatus, setFilterStatus] = useState("all");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // ====== Загрузка категорий с бэка ======
  useEffect(() => {
    async function loadCategories() {
      try {
        setLoading(true);
        setError("");
        const res = await fetch(`${API_BASE}/api/categories`);
        if (!res.ok) {
          throw new Error(`HTTP ${res.status}`);
        }
        const data = await res.json();
        const cats = data.categories || [];
        setCategories(cats);
        if (cats.length > 0) {
          setSelectedCategoryId(cats[0].id);
        }
      } catch (e) {
        console.error("Ошибка загрузки категорий", e);
        setError("Не удалось загрузить категории");
      } finally {
        setLoading(false);
      }
    }

    loadCategories();
  }, []);

  const selectedCategory = useMemo(
    () => categories.find((c) => c.id === selectedCategoryId) ?? null,
    [categories, selectedCategoryId]
  );

  const filteredCategories = useMemo(
    () =>
      categories.filter((cat) => {
        if (
          search &&
          !`${cat.name} ${cat.description || ""}`
            .toLowerCase()
            .includes(search.toLowerCase())
        ) {
          return false;
        }
        if (filterId && !String(cat.id).includes(filterId.trim())) return false;
        if (filterStatus !== "all" && cat.status !== filterStatus) return false;

        if (dateFrom && cat.createdAt) {
          if (new Date(cat.createdAt) < new Date(dateFrom)) return false;
        }
        if (dateTo && cat.createdAt) {
          if (new Date(cat.createdAt) > new Date(dateTo)) return false;
        }
        return true;
      }),
    [categories, search, filterId, filterStatus, dateFrom, dateTo]
  );

  const handleRegenerate = async (id) => {
    try {
      await fetch(`${API_BASE}/api/categories/${id}/regenerate`, {
        method: "POST",
      });
      alert(`Перегенерация категории ID ${id} (пока заглушка на бэке)`);
    } catch (e) {
      console.error("Ошибка перегенерации", e);
      alert("Не удалось отправить запрос на перегенерацию");
    }
  };

  const handleRatingChange = async (id, rating) => {
    // сначала оптимистично обновим фронт
    setCategories((prev) =>
      prev.map((c) => (c.id === id ? { ...c, rating } : c))
    );

    try {
      await fetch(`${API_BASE}/api/categories/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ rating }),
      });
    } catch (e) {
      console.error("Ошибка обновления рейтинга", e);
      // в проде можно сделать откат или показать тост
    }
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
            <span className="user-name">Администратор</span>
          </div>
          <div className="user-avatar">AD</div>
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
                  placeholder="Например, 793286151"
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
            {loading ? (
              <div className="table">
                <div className="table-empty">Загрузка категорий…</div>
              </div>
            ) : error ? (
              <div className="table">
                <div className="table-empty">{error}</div>
              </div>
            ) : (
              <table className="table">
                <thead>
                  <tr>
                    <th>ID категории</th>
                    <th>Название категории</th>
                    <th>Описание</th>
                    <th>Дата генерации</th>
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
                      <td className="cell-desc">
                        {cat.description || "—"}
                      </td>
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
                          value={cat.rating || 0}
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
            )}
          </div>
        </section>

        <section className="panel-right">
          {!selectedCategory ? (
            <div className="empty-card">
              {loading
                ? "Загрузка…"
                : "Выберите категорию в таблице слева"}
            </div>
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
  const rating = typeof value === "number" ? value : 0;

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
            (v <= rating ? "star-filled " : "") +
            (onChange ? "star-clickable" : "")
          }
          onClick={() => handleClick(v)}
        >
          ★
        </span>
      ))}
      <span className="stars-value">{rating.toFixed(1)}</span>
    </div>
  );
}

function CategoryCard({ category, onRegenerate, onRatingChange }) {
  const features = category.features || [];

  // Вытаскиваем цвета и размеры из признаков
  const colorsFeature = features.find((f) => f.key === "Цвет");
  const sizesFeature =
    features.find((f) => f.key === "Размер") ||
    features.find((f) => f.key === "Размер (RU)");

  const colors = colorsFeature?.values || [];
  const sizes = sizesFeature?.values || [];

  const [selectedColor, setSelectedColor] = useState(
    colors[0] || "—"
  );
  const [selectedSize, setSelectedSize] = useState(
    sizes[0] || "—"
  );

  // если категория поменялась — можно было бы сбросить стейт,
  // но компонент размонтируется и смонтируется заново, так что ок

  return (
    <div className="card">
      <div className="card-header">
        <div>
          <h2>{category.name}</h2>
          <div className="card-subtitle">
            ID категории: {category.id} · Сгенерировано:{" "}
            {formatDate(category.createdAt)}
          </div>
        </div>
        <div className="card-status-group">
          <span className="card-status-label">Статус:</span>
          {category.status === "approved" ? (
            <span className="badge badge-success">
              Одобрено администратором
            </span>
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
            <StarRating value={category.rating || 0} onChange={onRatingChange} />
          </div>

          <div className="card-section">
            <h3>Описание</h3>
            <p>{category.description || "Описание не задано"}</p>
          </div>

          <div className="card-section">
            <h3>Характеристики категории</h3>
            {features.length === 0 ? (
              <p>Нет выделенных характеристик для этой категории.</p>
            ) : (
              <ul style={{ margin: 0, paddingLeft: 16, fontSize: 13 }}>
                {features.map((f) => (
                  <li key={f.key}>
                    <b>{f.key}:</b>{" "}
                    {(f.values || []).join(", ")}
                  </li>
                ))}
              </ul>
            )}
          </div>

          {(colors.length > 0 || sizes.length > 0) && (
            <div className="card-section">
              <h3>Примеры вариаций товаров</h3>

              <div className="card-variants">
                {colors.length > 0 && (
                  <div className="variant-block">
                    <div className="variant-label">Цвет</div>
                    <div className="variant-options">
                      {colors.map((color) => (
                        <button
                          key={color}
                          className={
                            "chip " +
                            (color === selectedColor
                              ? "chip-selected"
                              : "")
                          }
                          onClick={() => setSelectedColor(color)}
                        >
                          {color}
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                {sizes.length > 0 && (
                  <div className="variant-block">
                    <div className="variant-label">Размер</div>
                    <div className="variant-options">
                      {sizes.map((size) => (
                        <button
                          key={size}
                          className={
                            "chip " +
                            (size === selectedSize
                              ? "chip-selected"
                              : "")
                          }
                          onClick={() => setSelectedSize(size)}
                        >
                          {size}
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                <div className="variant-summary">
                  Текущая вариация:{" "}
                  <b>{selectedColor}</b>
                  {sizes.length > 0 && (
                    <>
                      , размер <b>{selectedSize}</b>
                    </>
                  )}
                </div>
              </div>
            </div>
          )}

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
