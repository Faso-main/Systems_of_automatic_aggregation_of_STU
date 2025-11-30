// src/App.jsx
import React, { useMemo, useState, useEffect, useRef } from "react";
import "./styles.css";

const API_BASE = "https://faso312.ru";
const PAGE_SIZE = 10;

const formatDate = (iso) =>
  iso ? new Date(iso).toLocaleDateString("ru-RU") : "—";

const statusLabel = (status) => {
  if (status === "approved") return "Одобрено";
  if (status === "rejected") return "Не одобрено";
  return "Не обработано";
};

function App() {
  const [categories, setCategories] = useState([]);
  const [regeneratingIds, setRegeneratingIds] = useState(new Set());
  const [selectedCategoryId, setSelectedCategoryId] = useState(null);

  // поле поиска в фильтре (текст, который вводит пользователь)
  const [search, setSearch] = useState("");
  const [filterId, setFilterId] = useState("");
  const [filterStatus, setFilterStatus] = useState("all");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");

  const [currentPage, setCurrentPage] = useState(1);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // модалка с товарами
  const [productsModal, setProductsModal] = useState(null);

  // состояние для умного поиска, встроенного в фильтр
  const [smartLoading, setSmartLoading] = useState(false);
  const [smartError, setSmartError] = useState("");
  const [smartResultIds, setSmartResultIds] = useState([]); // ID категорий, найденных умным поиском
  const smartTimeoutRef = useRef(null);

  // ====== Загрузка категорий ======
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

  // при смене фильтров сбрасываем страницу
  useEffect(() => {
    setCurrentPage(1);
  }, [search, filterId, filterStatus, dateFrom, dateTo, categories, smartResultIds]);

  const selectedCategory = useMemo(
    () => categories.find((c) => c.id === selectedCategoryId) ?? null,
    [categories, selectedCategoryId]
  );

  // Фильтрация по локальным условиям + учёт результатов умного поиска
    const filteredCategories = useMemo(() => {
      // сначала как раньше — просто фильтруем
      const base = categories.filter((cat) => {
        // 1) если умный поиск вернул какие-то ID — показываем только их
        if (smartResultIds.length > 0 && !smartResultIds.includes(cat.id)) {
          return false;
        }

        // 2) обычный текстовый фильтр по name/description (работает, когда smartResultIds пустой)
        if (
          smartResultIds.length === 0 &&
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
      });

      // Если умный поиск активен — порядок НЕ меняем (всё как раньше)
      if (smartResultIds.length > 0) {
        return base;
      }

      // Если умный поиск не активен — поднимаем жёлтые категории наверх
      const sorted = [...base].sort((a, b) => {
        const aFlag = a.hasUntrainedItems ? 1 : 0;
        const bFlag = b.hasUntrainedItems ? 1 : 0;
        // хотим: hasUntrainedItems = true → выше
        if (aFlag === bFlag) return 0;
        return bFlag - aFlag; // b=1,a=0 → b выше, но мы сортируем так, что aFlag<bFlag => положительное → b после a? давай наоборот:
      });

      return sorted;
    }, [categories, search, filterId, filterStatus, dateFrom, dateTo, smartResultIds]);


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
    // помечаем категорию как "в процессе перегенерации"
    setRegeneratingIds((prev) => {
      const next = new Set(prev);
      next.add(id);
      return next;
    });

    try {
      const resp = await fetch(`${API_BASE}/api/categories/${id}/regenerate`, {
        method: "POST",
      });
      if (!resp.ok) {
        throw new Error(`HTTP ${resp.status}`);
      }

      alert(`Категория ID ${id} отправлена на перегенерацию`);

      // подтягиваем свежую категорию и обновляем state
      const catResp = await fetch(`${API_BASE}/api/categories/${id}`);
      if (catResp.ok) {
        const { category } = await catResp.json();
        setCategories((prev) =>
          prev.map((c) => (c.id === id ? { ...c, ...category } : c))
        );
      }
    } catch (e) {
      console.error("Ошибка перегенерации", e);
      alert("Не удалось отправить запрос на перегенерацию");
    } finally {
      // снимаем флаг "перегенерации" с категории
      setRegeneratingIds((prev) => {
        const next = new Set(prev);
        next.delete(id);
        return next;
      });
    }
  };

  const handleRatingChange = async (id, rating) => {
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

  const handleCategoryUpdate = async (id, updates) => {
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

  const cycleStatusFilter = () => {
    setFilterStatus((prev) => {
      if (prev === "all") return "pending";
      if (prev === "pending") return "approved";
      if (prev === "approved") return "rejected";
      return "all";
    });
    setCurrentPage(1);
  };

  // загрузка товаров для модалки
  const fetchProductsForModal = async (categoryId, productIds) => {
    if (!productIds || productIds.length === 0) {
      setProductsModal((prev) =>
        prev && prev.id === categoryId
          ? { ...prev, loading: false, products: [] }
          : prev
      );
      return;
    }

    try {
      const res = await fetch(`${API_BASE}/api/products/by-ids`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ids: productIds }),
      });

      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }

      const data = await res.json();
      const products = data.products || [];

      setProductsModal((prev) =>
        prev && prev.id === categoryId
          ? { ...prev, loading: false, products, error: "" }
          : prev
      );
    } catch (e) {
      console.error("Ошибка загрузки товаров", e);
      setProductsModal((prev) =>
        prev && prev.id === categoryId
          ? {
              ...prev,
              loading: false,
              error: "Не удалось загрузить товары категории",
            }
          : prev
      );
    }
  };

  const handleShowProductsModal = (category) => {
    if (!category) return;
    const ids = category.productIds || [];

    setProductsModal({
      id: category.id,
      name: category.name,
      productIds: ids,
      products: [],
      loading: true,
      error: "",
    });

    fetchProductsForModal(category.id, ids);
  };

  const handleCloseProductsModal = () => {
    setProductsModal(null);
  };

  // ====== Интегрированный умный поиск в поле фильтра ======
  const handleSmartSearchChange = (e) => {
    const q = e.target.value;
    setSearch(q);
    setSmartError("");

    if (smartTimeoutRef.current) {
      clearTimeout(smartTimeoutRef.current);
    }

    // если строка пустая — сбрасываем результаты умного поиска
    if (!q.trim()) {
      setSmartLoading(false);
      setSmartResultIds([]);
      return;
    }

    smartTimeoutRef.current = setTimeout(async () => {
      try {
        setSmartLoading(true);
        const params = new URLSearchParams({ q });
        const res = await fetch(
          `${API_BASE}/api/search/categories?${params.toString()}`
        );
        if (!res.ok) {
          throw new Error(`HTTP ${res.status}`);
        }
        const data = await res.json(); // [{id,name,score,...}]

        if (!Array.isArray(data) || data.length === 0) {
          setSmartError("Ничего не найдено");
          setSmartResultIds([]);
          return;
        }

        // сохраняем все найденные ID категорий для таблицы
        const ids = data.map((r) => r.id);
        setSmartResultIds(ids);

        // выбираем топ-результат справа
        const top = data[0];
        setSelectedCategoryId(top.id);

        // таблицу логично показывать с первой страницы
        setCurrentPage(1);
      } catch (err) {
        console.error("Ошибка умного поиска:", err);
        setSmartError("Ошибка поиска");
        setSmartResultIds([]);
      } finally {
        setSmartLoading(false);
      }
    }, 300);
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
            <span className="user-name">Личный кабинет</span>
            <span className="user-label">Администратор</span>
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
        {/* ЛЕВАЯ ПАНЕЛЬ */}
        <section className="panel-left">
          <div className="filters-block">
            <div className="filters-header">Фильтры</div>

            <div className="filters-row">
              <div className="filter-item wide">
                <label>Поиск по категории (умный поиск)</label>
                <input
                  className="input"
                  placeholder="Введите текст…"
                  value={search}
                  onChange={handleSmartSearchChange}
                />
                {smartLoading && (
                  <div className="smart-search-indicator">Поиск…</div>
                )}
                {smartError && (
                  <div className="smart-search-error">{smartError}</div>
                )}
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
                      <th>ID категории</th>
                      <th>Название категории</th>
                      <th>Описание</th>
                      <th>Дата генерации</th>
                      <th>Новые товары</th>
                      <th>
                        <div className="column-header">
                          <span className="column-header-label">Статус</span>
                          <div className="column-header-controls">
                            <button
                              className="status-filter-btn"
                              title="Цикл по статусам"
                              onClick={cycleStatusFilter}
                            >
                              ▲▼
                            </button>
                          </div>
                        </div>
                      </th>
                      <th>Оценка</th>
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
                          "table-row" +
                          (cat.id === selectedCategoryId ? " table-row--active" : "") +
                          (cat.hasUntrainedItems ? " table-row--warning" : "")
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

                          {cat.hasUntrainedItems && (
                            <div className="training-warning">
                              Необученных СТЕ: {cat.untrainedItemsCount}
                            </div>
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

        {/* ПРАВАЯ ПАНЕЛЬ */}
        <section className="panel-right">
          {selectedCategory ? (
            <CategoryCard
              category={selectedCategory}
              onRegenerate={handleRegenerate}
              onRatingChange={handleRatingChange}
              onUpdateCategory={handleCategoryUpdate}
              onShowProducts={() => handleShowProductsModal(selectedCategory)}
              isRegenerating={regeneratingIds.has(selectedCategory.id)}
            />
          ) : (
            <div className="card-empty">
              Выберите категорию слева, чтобы посмотреть детали
            </div>
          )}
        </section>
      </main>

      {productsModal && (
        <ProductsModal data={productsModal} onClose={handleCloseProductsModal} />
      )}
    </div>
  );
}

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

function CategoryCard({
  category,
  onRegenerate,
  onRatingChange,
  onUpdateCategory,
  onShowProducts,
  isRegenerating,
}) {
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

  useEffect(() => {
    setDescriptionDraft(description || "");
    setSaving(false);
  }, [id, description]);

  const handleSave = async () => {
    const updates = { description: descriptionDraft.trim() };

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
            <div className="card-title-text">{name}</div>
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

          {/* ─── НОВЫЙ БЛОК: Управление статусом ─────────────────────────────────────── */}
          <div className="card-status-toggle">
            <span className="status-toggle-label">Статус:</span>

            <button
              type="button"
              className={
                "status-toggle-btn" +
                (status === "approved" ? " status-toggle-btn--active" : "")
              }
              onClick={() => onUpdateCategory?.(id, { status: "approved" })}
            >
              Одобрено
            </button>

            <button
              type="button"
              className={
                "status-toggle-btn" +
                (status === "rejected" ? " status-toggle-btn--active" : "")
              }
              onClick={() => onUpdateCategory?.(id, { status: "rejected" })}
            >
              Не одобрено
            </button>
          </div>
          {/* ─────────────────────────────────────────────────────────────────────────── */}

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
              type="button"
              className="btn btn-ghost btn-small"
              onClick={() => onShowProducts?.()}
              disabled={!productIds || productIds.length === 0}
            >
              Показать все СТЕ
            </button>

            <button
              className="btn btn-primary"
              onClick={() => onRegenerate?.(id)}
              type="button"
              disabled={isRegenerating}
            >
              {isRegenerating ? "Перегенерация…" : "Перегенерировать категорию"}
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
              {features.map((f, idx) => {
                const values = Array.isArray(f.values)
                  ? f.values.join(", ")
                  : f.value ?? "";
                return (
                  <div key={`${f.key}-${idx}`} className="feature-pill">
                    <span className="feature-key">{f.key}</span>
                    <span className="feature-value">{values}</span>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        <div className="card-section">
          <div className="card-section-title">Товары в категории</div>
          <div className="products-count-row">
            <span className="products-count">
              Количество СТЕ в категории: {productIds?.length ?? 0}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

function ProductsModal({ data, onClose }) {
  if (!data) return null;
  const { name, productIds = [], products = [], loading, error } = data;

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div
        className="modal modal-wide"
        onClick={(e) => {
          e.stopPropagation();
        }}
      >
        <div className="modal-header">
          <h2 className="modal-title">СТЕ в категории «{name}»</h2>
          <button
            type="button"
            className="btn btn-ghost btn-small"
            onClick={onClose}
          >
            ✕
          </button>
        </div>

        <div className="modal-body">
          {loading ? (
            <p>Загрузка товаров…</p>
          ) : error ? (
            <p className="products-error">{error}</p>
          ) : productIds.length === 0 ? (
            <p>В этой категории пока нет СТЕ.</p>
          ) : products.length === 0 ? (
            <p>По указанным ID товаров в БД ничего не найдено.</p>
          ) : (
            <div className="products-table-wrapper">
              <table className="products-table">
                <thead>
                  <tr>
                    <th>ID</th>
                    <th>Наименование</th>
                    <th>Производитель</th>
                    <th>Страна</th>
                    <th>Характеристики</th>
                  </tr>
                </thead>
                <tbody>
                  {products.map((p) => {
                    const specsText =
                      typeof p.raw_specs === "string" ? p.raw_specs : "";
                    const specsLines = specsText
                      ? specsText
                          .split(";")
                          .map((s) => s.trim())
                          .filter(Boolean)
                      : [];

                    const untrained = p.is_used_for_training === false;

                    return (
                      <tr
                        key={p.id}
                        className={
                          untrained ? "product-row product-row--untrained" : "product-row"
                        }
                      >
                        <td className="products-col-id">{p.id}</td>
                        <td className="products-col-name">
                          {p.name || "—"}
                          {untrained && (
                            <span className="product-tag-untrained">
                              не использован в обучении
                            </span>
                          )}
                        </td>
                        <td className="products-col-producer">{p.producer || "—"}</td>
                        <td className="products-col-country">{p.country || "—"}</td>
                        <td className="products-col-specs">
                          {specsLines.length === 0 ? (
                            <span>—</span>
                          ) : (
                            specsLines.map((line, idx) => (
                              <div key={idx} className="products-spec-line">
                                {line}
                              </div>
                            ))
                          )}
                        </td>
                      </tr>
                    );
                  })}

                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default App;
