// src/App.jsx
import React, { useMemo, useState, useEffect } from "react";
import "./styles.css";

const API_BASE = "https://faso312.ru";
const PAGE_SIZE = 15; // 15 строк на странице

const formatDate = (iso) =>
  iso ? new Date(iso).toLocaleDateString("ru-RU") : "—";

const statusLabel = (status) => {
  if (status === "approved") return "Одобрено";
  if (status === "rejected") return "Не одобрено";
  return "Не обработано";
};

function App() {
  const [categories, setCategories] = useState([]);
  const [selectedCategoryId, setSelectedCategoryId] = useState(null);

  const [search, setSearch] = useState("");
  const [filterId, setFilterId] = useState("");
  const [filterStatus, setFilterStatus] = useState("all"); // all | pending | approved | rejected
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");

  const [currentPage, setCurrentPage] = useState(1);

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

  // сброс страницы при изменении фильтров
  useEffect(() => {
    setCurrentPage(1);
  }, [search, filterId, filterStatus, dateFrom, dateTo, categories]);

  const selectedCategory = useMemo(
    () => categories.find((c) => c.id === selectedCategoryId) ?? null,
    [categories, selectedCategoryId]
  );

  // Фильтрация по всей БД (по всему массиву categories)
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

        if (filterStatus !== "all") {
          if (filterStatus === "pending") {
            if (cat.status === "approved" || cat.status === "rejected") {
              return false;
            }
          } else if (cat.status !== filterStatus) {
            return false;
          }
        }

        const dateField = cat.createdAt || cat.generatedAt;
        if (dateFrom && dateField) {
          if (new Date(dateField) < new Date(dateFrom)) return false;
        }
        if (dateTo && dateField) {
          if (new Date(dateField) > new Date(dateTo)) return false;
        }

        return true;
      }),
    [categories, search, filterId, filterStatus, dateFrom, dateTo]
  );

  // Пагинация
  const totalPages = useMemo(
    () =>
      filteredCategories.length > 0
        ? Math.ceil(filteredCategories.length / PAGE_SIZE)
        : 1,
    [filteredCategories.length]
  );

  const paginatedCategories = useMemo(() => {
    const start = (currentPage - 1) * PAGE_SIZE;
    return filteredCategories.slice(start, start + PAGE_SIZE);
  }, [filteredCategories, currentPage]);

  const totalCount = categories.length;
  const filteredCount = filteredCategories.length;

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
    // оптимистично обновляем на фронте
    setCategories((prev) =>
      prev.map((c) => (c.id === id ? { ...c, rating } : c))
    );

    try {
      await fetch(`${API_BASE}/api/categories/${id}/rating`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ rating }),
      });
    } catch (e) {
      console.error("Ошибка сохранения рейтинга", e);
      alert("Не удалось сохранить рейтинг категории");
    }
  };

  // обновление имени / описания категории
  const handleCategoryUpdate = async (id, updates) => {
    // оптимистичное обновление
    setCategories((prev) =>
      prev.map((c) => (c.id === id ? { ...c, ...updates } : c))
    );

    try {
      await fetch(`${API_BASE}/api/categories/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(updates),
      });
    } catch (e) {
      console.error("Ошибка сохранения изменений категории", e);
      alert("Не удалось сохранить изменения категории");
    }
  };

  // клик по стрелочке в колонке «Статус» — быстрый цикл фильтра
  const cycleStatusFilter = () => {
    setFilterStatus((prev) => {
      if (prev === "all") return "pending";
      if (prev === "pending") return "approved";
      if (prev === "approved") return "rejected";
      return "all";
    });
    setCurrentPage(1);
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
          <div className="categories-count">
            Всего: {totalCount} • По фильтру: {filteredCount}
          </div>
        </div>
      </div>

      <main className="layout">
        {/* ЛЕВАЯ ПАНЕЛЬ: таблица категорий */}
        <section className="panel-left">
          <div className="filters-block">
            <div className="filters-header">Фильтры</div>

            <div className="filters-row">
              <div className="filter-item wide">
                <label>Поиск по названию или описанию</label>
                <input
                  className="input"
                  placeholder="Введите текст."
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
                  <option value="pending">Не обработано</option>
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
                <div className="table-empty table-empty-error">{error}</div>
              </div>
            ) : (
              <>
                <table className="table">
                  <thead>
                    <tr>
                      <th>
                        <div className="column-header">
                          <span className="column-header-label">
                            ID категории
                          </span>
                        </div>
                      </th>
                      <th>
                        <div className="column-header">
                          <span className="column-header-label">
                            Название категории
                          </span>
                        </div>
                      </th>
                      <th>
                        <div className="column-header">
                          <span className="column-header-label">Описание</span>
                        </div>
                      </th>
                      <th>
                        <div className="column-header">
                          <span className="column-header-label">
                            Дата генерации
                          </span>
                        </div>
                      </th>
                      <th>
                        <div className="column-header">
                          <span className="column-header-label">
                            Новые товары
                          </span>
                        </div>
                      </th>
                      <th>
                        <div className="column-header">
                          <span className="column-header-label">Статус</span>
                          <div className="column-header-controls">
                            <button
                              className="status-filter-btn"
                              title="Цикл по статусам: все → не обработано → одобрено → не одобрено"
                              onClick={cycleStatusFilter}
                            >
                              ▲▼
                            </button>
                          </div>
                        </div>
                      </th>
                      <th>
                        <div className="column-header">
                          <span className="column-header-label">Оценка</span>
                        </div>
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {paginatedCategories.length === 0 && (
                      <tr>
                        <td className="table-empty" colSpan={7}>
                          Нет категорий, подходящих под фильтр
                        </td>
                      </tr>
                    )}

                    {paginatedCategories.map((cat) => (
                      <tr
                        key={cat.id}
                        className={
                          cat.id === selectedCategoryId
                            ? "table-row table-row--active"
                            : "table-row"
                        }
                        onClick={() => setSelectedCategoryId(cat.id)}
                      >
                        <td>{cat.id}</td>
                        <td className="table-cell-name">{cat.name}</td>
                        <td className="table-cell-description">
                          {cat.description || "—"}
                        </td>
                        <td>{formatDate(cat.generatedAt || cat.createdAt)}</td>
                        <td>
                          {cat.hasNewItems ? (
                            <span className="new-items-badge">
                              Есть новые ({cat.newItemsCount ?? 0})
                            </span>
                          ) : (
                            <span className="new-items-badge new-items-badge--none">
                              Нет
                            </span>
                          )}
                        </td>
                        <td>
                          <span
                            className={`status-badge ${
                              cat.status === "approved"
                                ? "status-badge--approved"
                                : cat.status === "rejected"
                                ? "status-badge--rejected"
                                : "status-badge--pending"
                            }`}
                          >
                            {statusLabel(cat.status)}
                          </span>
                        </td>
                        <td>
                          <StarRating
                            value={cat.rating ?? 0}
                            onChange={(v) => handleRatingChange(cat.id, v)}
                          />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>

                <div className="pagination">
                  <div className="pagination-info">
                    Страница {currentPage} из {totalPages}
                  </div>
                  <div className="pagination-buttons">
                    <button
                      className="pagination-btn"
                      disabled={currentPage === 1}
                      onClick={() => setCurrentPage((p) => p - 1)}
                    >
                      ◀
                    </button>
                    {Array.from({ length: totalPages }, (_, i) => i + 1).map(
                      (page) => (
                        <button
                          key={page}
                          className={`pagination-btn ${
                            page === currentPage
                              ? "pagination-btn--active"
                              : ""
                          }`}
                          onClick={() => setCurrentPage(page)}
                        >
                          {page}
                        </button>
                      )
                    )}
                    <button
                      className="pagination-btn"
                      disabled={currentPage === totalPages}
                      onClick={() => setCurrentPage((p) => p + 1)}
                    >
                      ▶
                    </button>
                  </div>
                </div>
              </>
            )}
          </div>
        </section>

        {/* ПРАВАЯ ПАНЕЛЬ: карточка выбранной категории (редактируемая) */}
        <section className="panel-right">
          {selectedCategory ? (
            <CategoryCard
              category={selectedCategory}
              onRegenerate={handleRegenerate}
              onRatingChange={handleRatingChange}
              onUpdateCategory={handleCategoryUpdate}
            />
          ) : (
            <div className="card-empty">
              Выберите категорию слева, чтобы посмотреть детали
            </div>
          )}
        </section>
      </main>
    </div>
  );
}

// ====== КОМПОНЕНТ ОЦЕНКИ ЗВЁЗДАМИ ======
function StarRating({ value = 0, onChange }) {
  const stars = [1, 2, 3, 4, 5];
  return (
    <div className="stars">
      {stars.map((s) => (
        <button
          key={s}
          type="button"
          className={`star ${value >= s ? "star--active" : ""}`}
          onClick={(e) => {
            e.stopPropagation();
            onChange?.(s);
          }}
        >
          ★
        </button>
      ))}
    </div>
  );
}

// ====== КАРТОЧКА КАТЕГОРИИ (справа) ======
function CategoryCard({ category, onRegenerate, onRatingChange, onUpdateCategory }) {
  const {
    id,
    name,
    description,
    createdAt,
    generatedAt,
    status,
    rating,
    features = [],
    productIds = [],
    hasNewItems,
    newItemsCount,
  } = category;

  const [descriptionDraft, setDescriptionDraft] = useState(description || "");
  const [saving, setSaving] = useState(false);

  const dateToShow = generatedAt || createdAt;

  // когда выбираем другую категорию — сбрасываем драфты
  useEffect(() => {
    setDescriptionDraft(description || "");
    setSaving(false);
  }, [id, description]);

  const handleSave = async () => {
    const updates = {
      description: descriptionDraft.trim(),
    };

    try {
      setSaving(true);
      await onUpdateCategory?.(id, updates);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="category-card">
      <div className="card-header">
        <div className="card-header-row">
          <div className="card-title-block">
          <label className="card-field-label">Название категории</label>
          <div className="card-title-text">
            {name}
          </div>
          <div className="card-id">ID категории: {id}</div>
          </div>
          <div className="card-meta">
            <div className="card-date">
              Сгенерировано: {formatDate(dateToShow)}
            </div>
            <div className="card-status">
              <span
                className={`status-badge ${
                  status === "approved"
                    ? "status-badge--approved"
                    : status === "rejected"
                    ? "status-badge--rejected"
                    : "status-badge--pending"
                }`}
              >
                {statusLabel(status)}
              </span>
            </div>
          </div>
        </div>

        <div className="card-header-row card-header-row--bottom">
          <div className="card-rating-row">
            <span className="rating-label">Оценка категории:</span>
            <StarRating
              value={rating ?? 0}
              onChange={(v) => onRatingChange?.(id, v)}
            />
          </div>
          <div className="card-actions">
            {hasNewItems && (
              <div className="card-new-items-info">
                Новые товары в категории: {newItemsCount ?? 0}
              </div>
            )}
            <button
              className="btn btn-ghost btn-small"
              type="button"
              onClick={handleSave}
              disabled={saving}
            >
              {saving ? "Сохранение..." : "Сохранить изменения"}
            </button>
            <button
              className="btn btn-primary"
              onClick={() => onRegenerate?.(id)}
              type="button"
            >
              Перегенерировать категорию
            </button>
          </div>
        </div>
      </div>

      <div className="card-body">
        <div className="card-section">
          <div className="card-section-title">Краткое описание</div>
          <textarea
            className="input card-description-input"
            rows={4}
            placeholder="Опишите, что за категория и по каким признакам товары должны в неё попадать."
            value={descriptionDraft}
            onChange={(e) => setDescriptionDraft(e.target.value)}
          />
        </div>

        <div className="card-section">
          <div className="card-section-title">Основные характеристики</div>

          {features.length === 0 ? (
            <p className="card-section-empty">
              Для этой категории пока не выделены уникальные характеристики.
            </p>
          ) : (
            <div className="features-grid">
              {features.map((f, idx) => (
                <div key={`${f.key}-${idx}`} className="feature-pill">
                  <span className="feature-key">{f.key}</span>
                  <span className="feature-value">{f.value}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="card-section">
          <div className="card-section-title">Товары в категории</div>
          <div className="products-count">
            Количество СТЕ в категории: {productIds?.length ?? 0}
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;
