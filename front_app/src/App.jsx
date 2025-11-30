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
  const [filterProductId, setFilterProductId] = useState("");
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

  // фильтр по оценке (звёздам) в таблице категорий
  const [ratingFilterOpen, setRatingFilterOpen] = useState(false);
  const [ratingFilterValues, setRatingFilterValues] = useState(() => new Set());

  // Excel-фильтр: статус
  const [statusFilterOpen, setStatusFilterOpen] = useState(false);
  const [statusFilterValues, setStatusFilterValues] = useState(() => new Set());

  // Excel-фильтр: новые товары
  const [newItemsFilterOpen, setNewItemsFilterOpen] = useState(false);
  const [newItemsFilterValues, setNewItemsFilterValues] = useState(() => new Set());


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
  }, [search, filterId, filterProductId, dateFrom, dateTo, categories, smartResultIds, ratingFilterValues, statusFilterValues, newItemsFilterValues]);

  const selectedCategory = useMemo(
    () => categories.find((c) => c.id === selectedCategoryId) ?? null,
    [categories, selectedCategoryId]
  );

  // возможные значения рейтинга (кол-во звёзд) из категорий
  const ratingOptions = useMemo(() => {
    const set = new Set();
    categories.forEach((cat) => {
      const r = typeof cat.rating === "number" ? cat.rating : 0;
      set.add(String(r));
    });
    return Array.from(set).sort((a, b) => Number(a) - Number(b));
  }, [categories]);

  // уникальные статусы
  const statusOptions = useMemo(() => {
    const set = new Set();
    categories.forEach(cat => {
      set.add(cat.status || "pending");
    });
    return Array.from(set);
  }, [categories]);

  // уникальные значения "новые товары" (true / false)
  const newItemsOptions = ["yes", "no"];

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

      // 3) фильтр по ID
      if (filterId && !String(cat.id).includes(filterId.trim())) {
        return false;
      }

      // 4) фильтр по ID СТЕ (id_CTE) внутри категории
      if (filterProductId && filterProductId.trim()) {
        const q = filterProductId.trim();
        const ids = Array.isArray(cat.productIds) ? cat.productIds : [];
        const hasMatch = ids.some((pid) => String(pid || "").includes(q));

        if (!hasMatch) return false;
      }

      // 5) фильтр по дате
      const dateField = cat.createdAt || cat.generatedAt;
      if (dateFrom && dateField) {
        if (new Date(dateField) < new Date(dateFrom)) return false;
      }
      if (dateTo && dateField) {
        if (new Date(dateField) > new Date(dateTo)) return false;
      }

      // 6) фильтр по рейтингу (звёздочкам) из шапки таблицы
      if (ratingFilterValues.size > 0) {
        const key = String(
          typeof cat.rating === "number" ? cat.rating : 0
        );
        if (!ratingFilterValues.has(key)) return false;
      }
      // 7) фильтр по статусу (попап-фильтр)
      if (statusFilterValues.size > 0) {
        const key = cat.status || "pending";
        if (!statusFilterValues.has(key)) return false;
      }

      // 8) фильтр по новым товарам
      if (newItemsFilterValues.size > 0) {
        const key = cat.hasNewItems ? "yes" : "no";
        if (!newItemsFilterValues.has(key)) return false;
      }

      return true;
    });

    // Если умный поиск активен — порядок НЕ меняем (всё как раньше)
    if (smartResultIds.length > 0) {
      return base;
    }

    // Если умный поиск не активен — поднимаем жёлтые категории наверх
    const sorted = [...base].sort((a, b) => {
      if (a.hasUntrainedItems === b.hasUntrainedItems) return 0;
      return a.hasUntrainedItems ? -1 : 1;
    });

    return sorted;
    }, [
      categories,
      search,
      filterId,
      filterProductId,
      dateFrom,
      dateTo,
      smartResultIds,
      ratingFilterValues,
      statusFilterValues,
      newItemsFilterValues,
    ]);


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

  const handleRegenerate = async (id, productIds) => {
    setRegeneratingIds((prev) => {
      const next = new Set(prev);
      next.add(id);
      return next;
    });

    try {
      const payload =
        Array.isArray(productIds) && productIds.length > 0
          ? { product_ids: productIds }
          : {};

      const resp = await fetch(`${API_BASE}/api/categories/${id}/regenerate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!resp.ok) {
        throw new Error(`HTTP ${resp.status}`);
      }

      alert(
        productIds && productIds.length
          ? `Категория ID ${id} отправлена на перегенерацию (товаров: ${productIds.length})`
          : `Категория ID ${id} отправлена на перегенерацию (все товары)`
      );

      // подтягиваем свежую категорию
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
                <label>ID СТЕ (товара)</label>
                <input
                  className="input"
                  placeholder="Например, 123456"
                  value={filterProductId}
                  onChange={(e) => setFilterProductId(e.target.value)}
                />
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
                      <th>
                        <div className="col-header-with-filter">
                          <span>Новые товары</span>
                          <button
                            type="button"
                            className={
                              newItemsFilterValues.size > 0
                                ? "col-filter-trigger col-filter-trigger--active"
                                : "col-filter-trigger"
                            }
                            onClick={(e) => {
                              e.stopPropagation();
                              setNewItemsFilterOpen(v => !v);
                            }}
                          >
                            ▾
                          </button>

                          {newItemsFilterOpen && (
                            <div className="col-filter-popover">
                              <div className="col-filter-popover-header">Фильтр по новым товарам</div>

                              <div className="col-filter-actions">
                                <button
                                  className="col-filter-link"
                                  onClick={() => setNewItemsFilterValues(new Set(newItemsOptions))}
                                >
                                  Выбрать все
                                </button>
                                <button
                                  className="col-filter-link"
                                  onClick={() => setNewItemsFilterValues(new Set())}
                                >
                                  Сбросить
                                </button>
                              </div>

                              <div className="col-filter-options">
                                <label className="col-filter-option">
                                  <input
                                    type="checkbox"
                                    checked={newItemsFilterValues.has("yes")}
                                    onChange={(e) =>
                                      setNewItemsFilterValues(prev => {
                                        const next = new Set(prev);
                                        if (e.target.checked) next.add("yes");
                                        else next.delete("yes");
                                        return next;
                                      })
                                    }
                                  />
                                  <span>Есть новые</span>
                                </label>

                                <label className="col-filter-option">
                                  <input
                                    type="checkbox"
                                    checked={newItemsFilterValues.has("no")}
                                    onChange={(e) =>
                                      setNewItemsFilterValues(prev => {
                                        const next = new Set(prev);
                                        if (e.target.checked) next.add("no");
                                        else next.delete("no");
                                        return next;
                                      })
                                    }
                                  />
                                  <span>Нет</span>
                                </label>
                              </div>
                            </div>
                          )}
                        </div>
                      </th>

                      <th>
                        <div className="col-header-with-filter">
                          <span>Статус</span>
                          <button
                            type="button"
                            className={
                              statusFilterValues.size > 0
                                ? "col-filter-trigger col-filter-trigger--active"
                                : "col-filter-trigger"
                            }
                            onClick={(e) => {
                              e.stopPropagation();
                              setStatusFilterOpen(v => !v);
                            }}
                          >
                            ▾
                          </button>

                          {statusFilterOpen && (
                            <div className="col-filter-popover">
                              <div className="col-filter-popover-header">Фильтр по статусу</div>

                              <div className="col-filter-actions">
                                <button
                                  className="col-filter-link"
                                  onClick={() => setStatusFilterValues(new Set(statusOptions))}
                                >
                                  Выбрать все
                                </button>
                                <button
                                  className="col-filter-link"
                                  onClick={() => setStatusFilterValues(new Set())}
                                >
                                  Сбросить
                                </button>
                              </div>

                              <div className="col-filter-options">
                                {statusOptions.map((key) => (
                                  <label key={key} className="col-filter-option">
                                    <input
                                      type="checkbox"
                                      checked={statusFilterValues.has(key)}
                                      onChange={(e) =>
                                        setStatusFilterValues(prev => {
                                          const next = new Set(prev);
                                          if (e.target.checked) next.add(key);
                                          else next.delete(key);
                                          return next;
                                        })
                                      }
                                    />
                                    <span>{statusLabel(key)}</span>
                                  </label>
                                ))}
                              </div>
                            </div>
                          )}
                        </div>
                      </th>

                      <th>
                        <div className="col-header-with-filter">
                          <span>Оценка</span>
                          <button
                            type="button"
                            className={
                              ratingFilterValues.size > 0
                                ? "col-filter-trigger col-filter-trigger--active"
                                : "col-filter-trigger"
                            }
                            onClick={(e) => {
                              e.stopPropagation();
                              setRatingFilterOpen((v) => !v);
                            }}
                          >
                            ▾
                          </button>

                          {ratingFilterOpen && (
                            <div className="col-filter-popover">
                              <div className="col-filter-popover-header">
                                Фильтр по оценке
                              </div>

                              <div className="col-filter-actions">
                                <button
                                  type="button"
                                  className="col-filter-link"
                                  onClick={() =>
                                    setRatingFilterValues(
                                      new Set(ratingOptions)
                                    )
                                  }
                                >
                                  Выбрать все
                                </button>
                                <button
                                  type="button"
                                  className="col-filter-link"
                                  onClick={() =>
                                    setRatingFilterValues(new Set())
                                  }
                                >
                                  Сбросить
                                </button>
                              </div>

                              <div className="col-filter-options">
                                {ratingOptions.map((key) => {
                                  const checked =
                                    ratingFilterValues.has(key);
                                  const num = Number(key);
                                  const label =
                                    num === 0 ? "Без оценки" : `${num} ★`;

                                  return (
                                    <label
                                      key={key}
                                      className="col-filter-option"
                                    >
                                      <input
                                        type="checkbox"
                                        checked={checked}
                                        onChange={(e) =>
                                          setRatingFilterValues((prev) => {
                                            const next = new Set(prev);
                                            if (e.target.checked) {
                                              next.add(key);
                                            } else {
                                              next.delete(key);
                                            }
                                            return next;
                                          })
                                        }
                                      />
                                      <span>{label}</span>
                                    </label>
                                  );
                                })}
                              </div>
                            </div>
                          )}
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
        <ProductsModal
          data={productsModal}
          onClose={handleCloseProductsModal}
          onRegenerateSelected={handleRegenerate}
        />
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

          {/* Управление статусом */}
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

function ProductsModal({ data, onClose, onRegenerateSelected }) {
  const {
    id: categoryId,
    name,
    productIds = [],
    products = [],
    loading,
    error,
  } = data || {};

  const [selectedIds, setSelectedIds] = useState(new Set(productIds));

  // Глобальный поиск
  const [searchText, setSearchText] = useState("");

  // Фильтры-«чекбоксы» по производителю и стране
  const [producerFilterOpen, setProducerFilterOpen] = useState(false);
  const [countryFilterOpen, setCountryFilterOpen] = useState(false);
  const [producerFilterValues, setProducerFilterValues] = useState(
    () => new Set()
  );
  const [countryFilterValues, setCountryFilterValues] = useState(
    () => new Set()
  );

  const EMPTY_KEY = "__EMPTY__";

  const normalizeOptionKey = (value) => {
    const v = (value || "").toString().trim();
    return v === "" ? EMPTY_KEY : v;
  };

  const getOptionLabel = (key) => {
    if (key === EMPTY_KEY) return "пусто";
    return key;
  };

  useEffect(() => {
    // При смене категории — сбрасываем выбор и фильтры
    setSelectedIds(new Set(productIds));
    setSearchText("");
    setProducerFilterOpen(false);
    setCountryFilterOpen(false);
    setProducerFilterValues(new Set());
    setCountryFilterValues(new Set());
  }, [categoryId, productIds]);

  // Уникальные значения для фильтров
  const producerOptions = useMemo(() => {
    const set = new Set();
    (products || []).forEach((p) => {
      set.add(normalizeOptionKey(p.producer));
    });
    return Array.from(set).sort((a, b) =>
      getOptionLabel(a).localeCompare(getOptionLabel(b), "ru", {
        sensitivity: "base",
      })
    );
  }, [products]);

  const countryOptions = useMemo(() => {
    const set = new Set();
    (products || []).forEach((p) => {
      set.add(normalizeOptionKey(p.country));
    });
    return Array.from(set).sort((a, b) =>
      getOptionLabel(a).localeCompare(getOptionLabel(b), "ru", {
        sensitivity: "base",
      })
    );
  }, [products]);

  // Применяем фильтры
  const filteredProducts = useMemo(() => {
    let list = products || [];
    if (!list.length) return [];

    const q = searchText.trim().toLowerCase();
    const producerSet = producerFilterValues;
    const countrySet = countryFilterValues;

    return list.filter((p) => {
      const specsText =
        typeof p.raw_specs === "string" ? p.raw_specs.toLowerCase() : "";

      // Глобальный поиск по ID, имени, производителю, стране, характеристикам
      if (q) {
        const haystack = [
          String(p.id || ""),
          p.name || "",
          p.producer || "",
          p.country || "",
          specsText || "",
        ]
          .join(" ")
          .toLowerCase();

        if (!haystack.includes(q)) return false;
      }

      // Фильтр по производителю (чекбоксы)
      if (producerSet.size > 0) {
        const key = normalizeOptionKey(p.producer);
        if (!producerSet.has(key)) return false;
      }

      // Фильтр по стране (чекбоксы)
      if (countrySet.size > 0) {
        const key = normalizeOptionKey(p.country);
        if (!countrySet.has(key)) return false;
      }

      return true;
    });
  }, [products, searchText, producerFilterValues, countryFilterValues]);

  const toggleOne = (pid, checked) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (checked) next.add(pid);
      else next.delete(pid);
      return next;
    });
  };

  // «Выделить всё» только по видимым строкам
  const allVisibleChecked =
    filteredProducts.length > 0 &&
    filteredProducts.every((p) => selectedIds.has(p.id));

  const toggleAll = (checked) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (checked) {
        filteredProducts.forEach((p) => next.add(p.id));
      } else {
        filteredProducts.forEach((p) => next.delete(p.id));
      }
      return next;
    });
  };

  const handleRegenerateClick = async () => {
    const ids = Array.from(selectedIds);
    if (ids.length === 0) {
      if (
        !window.confirm(
          "Вы не выбрали ни одного товара. Перегенерировать по ВСЕМ товарам категории?"
        )
      ) {
        return;
      }
      await onRegenerateSelected?.(categoryId); // без списка → все товары
    } else {
      await onRegenerateSelected?.(categoryId, ids);
    }
    onClose();
  };

  // Управление чекбоксами в попапе фильтра
  const toggleFilterValue = (kind, key, checked) => {
    const updater =
      kind === "producer" ? setProducerFilterValues : setCountryFilterValues;

    updater((prev) => {
      const next = new Set(prev);
      if (checked) next.add(key);
      else next.delete(key);
      return next;
    });
  };

  const selectAllFilterValues = (kind, options) => {
    const updater =
      kind === "producer" ? setProducerFilterValues : setCountryFilterValues;
    updater(new Set(options));
  };

  const clearFilterValues = (kind) => {
    const updater =
      kind === "producer" ? setProducerFilterValues : setCountryFilterValues;
    updater(new Set());
  };

  if (!data) return null;

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
            <>
              {/* Глобальный поиск по таблице */}
            <div className="modal-filters">
              <div className="modal-filters-counter modal-filters-counter--top">
                Всего: {products.length} • По фильтру: {filteredProducts.length}
              </div>

              <div className="modal-filters-main">
                <label className="modal-filters-label">
                  Поиск по таблице (ID, наименование, производитель, страна, характеристики)
                </label>
                <input
                  className="input modal-filters-input"
                  placeholder="Введите текст для поиска…"
                  value={searchText}
                  onChange={(e) => setSearchText(e.target.value)}
                />
              </div>
            </div>


              <div className="products-table-wrapper">
                <table className="products-table">
                  <thead>
                    <tr>
                      <th className="products-col-checkbox">
                        <input
                          type="checkbox"
                          checked={
                            filteredProducts.length > 0 && allVisibleChecked
                          }
                          onChange={(e) => toggleAll(e.target.checked)}
                        />
                      </th>
                      <th>ID</th>
                      <th>Наименование</th>
                      <th>
                        <div className="col-header-with-filter">
                          <span>Производитель</span>
                          <button
                            type="button"
                            className={
                              producerFilterValues.size > 0
                                ? "col-filter-trigger col-filter-trigger--active"
                                : "col-filter-trigger"
                            }
                            onClick={() =>
                              setProducerFilterOpen((v) => !v)
                            }
                          >
                            ▾
                          </button>
                          {producerFilterOpen && (
                            <div className="col-filter-popover">
                              <div className="col-filter-popover-header">
                                <span>Фильтр по производителю</span>
                              </div>
                              <div className="col-filter-actions">
                                <button
                                  type="button"
                                  className="col-filter-link"
                                  onClick={() =>
                                    selectAllFilterValues(
                                      "producer",
                                      producerOptions
                                    )
                                  }
                                >
                                  Выбрать все
                                </button>
                                <button
                                  type="button"
                                  className="col-filter-link"
                                  onClick={() =>
                                    clearFilterValues("producer")
                                  }
                                >
                                  Сбросить
                                </button>
                              </div>
                              <div className="col-filter-options">
                                {producerOptions.map((key) => {
                                  const label = getOptionLabel(key);
                                  const checked =
                                    producerFilterValues.has(key);
                                  return (
                                    <label
                                      key={key}
                                      className="col-filter-option"
                                    >
                                      <input
                                        type="checkbox"
                                        checked={checked}
                                        onChange={(e) =>
                                          toggleFilterValue(
                                            "producer",
                                            key,
                                            e.target.checked
                                          )
                                        }
                                      />
                                      <span>{label}</span>
                                    </label>
                                  );
                                })}
                              </div>
                            </div>
                          )}
                        </div>
                      </th>
                      <th>
                        <div className="col-header-with-filter">
                          <span>Страна</span>
                          <button
                            type="button"
                            className={
                              countryFilterValues.size > 0
                                ? "col-filter-trigger col-filter-trigger--active"
                                : "col-filter-trigger"
                            }
                            onClick={() => setCountryFilterOpen((v) => !v)}
                          >
                            ▾
                          </button>
                          {countryFilterOpen && (
                            <div className="col-filter-popover">
                              <div className="col-filter-popover-header">
                                <span>Фильтр по стране</span>
                              </div>
                              <div className="col-filter-actions">
                                <button
                                  type="button"
                                  className="col-filter-link"
                                  onClick={() =>
                                    selectAllFilterValues(
                                      "country",
                                      countryOptions
                                    )
                                  }
                                >
                                  Выбрать все
                                </button>
                                <button
                                  type="button"
                                  className="col-filter-link"
                                  onClick={() =>
                                    clearFilterValues("country")
                                  }
                                >
                                  Сбросить
                                </button>
                              </div>
                              <div className="col-filter-options">
                                {countryOptions.map((key) => {
                                  const label = getOptionLabel(key);
                                  const checked = countryFilterValues.has(key);
                                  return (
                                    <label
                                      key={key}
                                      className="col-filter-option"
                                    >
                                      <input
                                        type="checkbox"
                                        checked={checked}
                                        onChange={(e) =>
                                          toggleFilterValue(
                                            "country",
                                            key,
                                            e.target.checked
                                          )
                                        }
                                      />
                                      <span>{label}</span>
                                    </label>
                                  );
                                })}
                              </div>
                            </div>
                          )}
                        </div>
                      </th>
                      <th>Характеристики</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredProducts.length === 0 ? (
                      <tr>
                        <td colSpan={6} className="table-empty">
                          Нет товаров, подходящих под фильтр
                        </td>
                      </tr>
                    ) : (
                      filteredProducts.map((p) => {
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
                              untrained
                                ? "product-row product-row--untrained"
                                : "product-row"
                            }
                          >
                            <td className="products-col-checkbox">
                              <input
                                type="checkbox"
                                checked={selectedIds.has(p.id)}
                                onChange={(e) =>
                                  toggleOne(p.id, e.target.checked)
                                }
                              />
                            </td>
                            <td className="products-col-id">{p.id}</td>
                            <td className="products-col-name">
                              {p.name || "—"}
                              {untrained && (
                                <span className="product-tag-untrained">
                                  не использован в обучении
                                </span>
                              )}
                            </td>
                            <td className="products-col-producer">
                              {p.producer || "—"}
                            </td>
                            <td className="products-col-country">
                              {p.country || "—"}
                            </td>
                            <td className="products-col-specs">
                              {specsLines.length === 0 ? (
                                <span>—</span>
                              ) : (
                                specsLines.map((line, idx) => (
                                  <div
                                    key={idx}
                                    className="products-spec-line"
                                  >
                                    {line}
                                  </div>
                                ))
                              )}
                            </td>
                          </tr>
                        );
                      })
                    )}
                  </tbody>
                </table>
              </div>

              <div className="modal-footer">
                <div className="modal-footer-info">
                  Выбрано товаров: {selectedIds.size} из {products.length}
                </div>
                <button
                  type="button"
                  className="btn btn-primary"
                  onClick={handleRegenerateClick}
                >
                  Перегенерировать по выбранным
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}



export default App;
