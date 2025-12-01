/* eslint-disable no-unused-vars */
// App.jsx — обновлённый стиль, мягкий рефакторинг
import React, {
  useMemo,
  useState,
  useEffect,
  useRef
} from "react";
import "./styles.css";

const API_BASE = "https://faso312.ru";
const PAGE_SIZE = 10;

const formatDate = (iso) =>
  iso ? new Date(iso).toLocaleDateString("ru-RU") : "—";

const statusLabel = (value) => {
  switch (value) {
    case "approved":
      return "Одобрено";
    case "rejected":
      return "Не одобрено";
    default:
      return "Не обработано";
  }
};

function App() {
  const [categories, setCategories] = useState([]);
  const [selectedId, setSelectedId] = useState(null);

  // фильтры
  const [search, setSearch] = useState("");
  const [filterId, setFilterId] = useState("");
  const [filterProductId, setFilterProductId] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");

  const [currentPage, setCurrentPage] = useState(1);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // товары модалки
  const [productsView, setProductsView] = useState(null);
  const [familyView, setFamilyView] = useState(null);

  // умный поиск
  const [smartLoading, setSmartLoading] = useState(false);
  const [smartError, setSmartError] = useState("");
  const [smartHits, setSmartHits] = useState([]);
  const smartTimer = useRef(null);

  // фильтры рейтинга / статуса / новых товаров
  const [ratingPopup, setRatingPopup] = useState(false);
  const [ratingFilter, setRatingFilter] = useState(() => new Set());

  const [statusPopup, setStatusPopup] = useState(false);
  const [statusFilter, setStatusFilter] = useState(() => new Set());

  const [newPopup, setNewPopup] = useState(false);
  const [newFilter, setNewFilter] = useState(() => new Set());

  const [processing, setProcessing] = useState(new Set());

  // -------------------------
  // Загрузка категорий
  // -------------------------
  useEffect(() => {
    const load = async () => {
      try {
        setLoading(true);
        const res = await fetch(`${API_BASE}/api/categories`);
        if (!res.ok) throw new Error(res.status);

        const body = await res.json();
        const list = body.categories || [];

        setCategories(list);
        if (list.length) setSelectedId(list[0].id);

      } catch (err) {
        console.error("Ошибка загрузки категорий:", err);
        setError("Не удалось загрузить категории");
      } finally {
        setLoading(false);
      }
    };

    load();
  }, []);

  // при смене фильтров — на первую страницу
  useEffect(() => {
    setCurrentPage(1);
  }, [
    search,
    filterId,
    filterProductId,
    dateFrom,
    dateTo,
    categories,
    smartHits,
    ratingFilter,
    statusFilter,
    newFilter
  ]);

  const selectedCategory = useMemo(
    () => categories.find((c) => c.id === selectedId) || null,
    [categories, selectedId]
  );

  // подготовка значений рейтинга для фильтра
  const ratingOptions = useMemo(() => {
    const s = new Set();
    categories.forEach((c) => {
      const r = typeof c.rating === "number" ? c.rating : 0;
      s.add(String(r));
    });
    return [...s].sort((a, b) => Number(a) - Number(b));
  }, [categories]);

  // уникальные статусы
  const statusOptions = useMemo(() => {
    const s = new Set();
    categories.forEach((c) => s.add(c.status || "pending"));
    return [...s];
  }, [categories]);

  const newOptions = ["yes", "no"];
  // -------------------------
  // Фильтрация категорий
  // -------------------------
  const filteredCategories = useMemo(() => {
    const base = categories.filter((c) => {
      // если умный поиск дал конкретные совпадения — показываем только их
      if (smartHits.length && !smartHits.includes(c.id)) return false;

      // обычный поиск по тексту, когда умный не активен
      if (!smartHits.length && search) {
        const text = `${c.name} ${c.description || ""}`.toLowerCase();
        if (!text.includes(search.toLowerCase())) return false;
      }

      if (filterId && !String(c.id).includes(filterId)) return false;

      if (filterProductId) {
        const ids = Array.isArray(c.productIds) ? c.productIds : [];
        const ok = ids.some((p) =>
          String(p || "").includes(filterProductId.trim())
        );
        if (!ok) return false;
      }

      const d = c.createdAt || c.generatedAt;
      if (dateFrom && d && new Date(d) < new Date(dateFrom)) return false;
      if (dateTo && d && new Date(d) > new Date(dateTo)) return false;

      if (ratingFilter.size) {
        const r = String(typeof c.rating === "number" ? c.rating : 0);
        if (!ratingFilter.has(r)) return false;
      }

      if (statusFilter.size) {
        const s = c.status || "pending";
        if (!statusFilter.has(s)) return false;
      }

      if (newFilter.size) {
        const flag = c.hasNewItems ? "yes" : "no";
        if (!newFilter.has(flag)) return false;
      }

      return true;
    });

    // если умный поиск активен — сортировку не меняем
    if (smartHits.length) return base;

    // поднимаем категории с необученными товарами
    return [...base].sort((a, b) => {
      if (a.hasUntrainedItems === b.hasUntrainedItems) return 0;
      return a.hasUntrainedItems ? -1 : 1;
    });
  }, [
    categories,
    search,
    filterId,
    filterProductId,
    dateFrom,
    dateTo,
    smartHits,
    ratingFilter,
    statusFilter,
    newFilter
  ]);

  const totalPages = Math.max(1, Math.ceil(filteredCategories.length / PAGE_SIZE));

  const paginated = useMemo(() => {
    const start = (currentPage - 1) * PAGE_SIZE;
    return filteredCategories.slice(start, start + PAGE_SIZE);
  }, [filteredCategories, currentPage]);

  const totalCount = categories.length;
  const filteredCount = filteredCategories.length;

  // -------------------------
  // Перегенерация категории
  // -------------------------
  const regenerateCategory = async (id, productIds) => {
    setProcessing((old) => new Set(old).add(id));

    try {
      const payload =
        Array.isArray(productIds) && productIds.length
          ? { product_ids: productIds }
          : {};

      const resp = await fetch(
        `${API_BASE}/api/categories/${id}/regenerate`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        }
      );

      if (!resp.ok) throw new Error("bad response");

      // обновляем категорию после перегенерации
      try {
        const fresh = await fetch(`${API_BASE}/api/categories/${id}`);
        if (fresh.ok) {
          const { category } = await fresh.json();
          setCategories((list) =>
            list.map((c) => (c.id === id ? { ...c, ...category } : c))
          );
        }
      } catch (err) {
        console.warn("Не удалось обновить категорию:", err);
      }
    } catch (err) {
      console.error("Ошибка перегенерации:", err);
      alert("Не удалось выполнить перегенерацию");
    } finally {
      setProcessing((old) => {
        const next = new Set(old);
        next.delete(id);
        return next;
      });
    }
  };

  // -------------------------
  // Изменение рейтинга
  // -------------------------
  const updateRating = async (id, rating) => {
    setCategories((prev) =>
      prev.map((c) => (c.id === id ? { ...c, rating } : c))
    );

    try {
      await fetch(`${API_BASE}/api/categories/${id}/rating`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ rating })
      });
    } catch (err) {
      console.error("Ошибка сохранения рейтинга", err);
    }
  };

  // -------------------------
  // Частичное обновление категории
  // -------------------------
  const saveCategoryPatch = async (id, patch) => {
    setCategories((prev) =>
      prev.map((c) => (c.id === id ? { ...c, ...patch } : c))
    );

    try {
      await fetch(`${API_BASE}/api/categories/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(patch)
      });
    } catch (err) {
      console.error("Ошибка PATCH", err);
    }
  };
  // -------------------------
  // Модалка "Семейство"
  // -------------------------
  const openFamily = async (category) => {
    if (!category) return;

    const { id, name } = category;

    setFamilyView({
      categoryId: id,
      categoryName: name,
      familyId: null,
      familyName: "",
      loading: true,
      error: "",
      members: []
    });

    try {
      const res = await fetch(`${API_BASE}/api/categories/${id}/family`);
      if (!res.ok) throw new Error(res.status);

      const body = await res.json();
      setFamilyView({
        categoryId: id,
        categoryName: name,
        familyId: body.family?.id || null,
        familyName: body.family?.name || "",
        loading: false,
        error: "",
        members: Array.isArray(body.members) ? body.members : []
      });
    } catch (err) {
      setFamilyView((prev) => ({
        ...(prev || {}),
        loading: false,
        error: "Не удалось загрузить семейство",
        members: []
      }));
    }
  };

  const closeFamily = () => setFamilyView(null);

  // -------------------------
  // Модалка "Товары"
  // -------------------------
  const fetchProducts = async (id, ids) => {
    if (!ids?.length) {
      setProductsView((v) =>
        v && v.id === id ? { ...v, loading: false, products: [] } : v
      );
      return;
    }

    try {
      const res = await fetch(`${API_BASE}/api/products/by-ids`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ids })
      });

      if (!res.ok) throw new Error(res.status);

      const body = await res.json();
      setProductsView((v) =>
        v && v.id === id
          ? { ...v, loading: false, products: body.products || [], error: "" }
          : v
      );
    } catch (err) {
      setProductsView((v) =>
        v && v.id === id
          ? { ...v, loading: false, error: "Не удалось загрузить товары" }
          : v
      );
    }
  };

  const openProducts = (category) => {
    if (!category) return;

    const ids = category.productIds || [];

    setProductsView({
      id: category.id,
      name: category.name,
      productIds: ids,
      products: [],
      loading: true,
      error: ""
    });

    fetchProducts(category.id, ids);
  };

  const closeProducts = () => setProductsView(null);

  // -------------------------
  // Умный поиск (интегрирован в фильтры)
  // -------------------------
  const smartSearch = (e) => {
    const q = e.target.value.trim();
    setSearch(e.target.value);
    setSmartError("");

    if (smartTimer.current) clearTimeout(smartTimer.current);

    if (!q) {
      setSmartHits([]);
      setSmartLoading(false);
      return;
    }

    smartTimer.current = setTimeout(async () => {
      try {
        setSmartLoading(true);
        const res = await fetch(
          `${API_BASE}/api/search/categories?q=${encodeURIComponent(q)}`
        );
        if (!res.ok) throw new Error(res.status);

        const data = await res.json();
        if (!Array.isArray(data) || !data.length) {
          setSmartError("Ничего не найдено");
          setSmartHits([]);
          return;
        }

        const ids = data.map((x) => x.id);
        setSmartHits(ids);
        setSelectedId(data[0].id);
        setCurrentPage(1);

      } catch (err) {
        setSmartError("Ошибка поиска");
        setSmartHits([]);
      } finally {
        setSmartLoading(false);
      }
    }, 300);
  };

  // -------------------------
  // Рендер
  // -------------------------
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
        {/* левая панель */}
        <section className="panel-left">
          <div className="filters-block">
            <div className="filters-header">Фильтры</div>

            <div className="filters-row">
              <div className="filter-item wide">
                <label>Поиск по категории</label>
                <input
                  className="input"
                  placeholder="Введите текст…"
                  value={search}
                  onChange={smartSearch}
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
                  value={filterId}
                  onChange={(e) => setFilterId(e.target.value)}
                  placeholder="Например, 793286151"
                />
              </div>

              <div className="filter-item">
                <label>ID СТЕ (товара)</label>
                <input
                  className="input"
                  value={filterProductId}
                  onChange={(e) => setFilterProductId(e.target.value)}
                  placeholder="Например, 123456"
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
          {/* таблица */}
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

                      {/* Новые товары */}
                      <th>
                        <div className="col-header-with-filter">
                          <span>Новые товары</span>

                          <button
                            type="button"
                            className={
                              newFilter.size
                                ? "col-filter-trigger col-filter-trigger--active"
                                : "col-filter-trigger"
                            }
                            onClick={(e) => {
                              e.stopPropagation();
                              setNewPopup((v) => !v);
                            }}
                          >
                            ▾
                          </button>

                          {newPopup && (
                            <div className="col-filter-popover">
                              <div className="col-filter-popover-header">
                                Фильтр по новым товарам
                              </div>

                              <div className="col-filter-actions">
                                <button
                                  className="col-filter-link"
                                  onClick={() => setNewFilter(new Set(newOptions))}
                                >
                                  Выбрать все
                                </button>
                                <button
                                  className="col-filter-link"
                                  onClick={() => setNewFilter(new Set())}
                                >
                                  Сбросить
                                </button>
                              </div>

                              <div className="col-filter-options">
                                <label className="col-filter-option">
                                  <input
                                    type="checkbox"
                                    checked={newFilter.has("yes")}
                                    onChange={(e) =>
                                      setNewFilter((s) => {
                                        const next = new Set(s);
                                        e.target.checked
                                          ? next.add("yes")
                                          : next.delete("yes");
                                        return next;
                                      })
                                    }
                                  />
                                  <span>Есть новые</span>
                                </label>

                                <label className="col-filter-option">
                                  <input
                                    type="checkbox"
                                    checked={newFilter.has("no")}
                                    onChange={(e) =>
                                      setNewFilter((s) => {
                                        const next = new Set(s);
                                        e.target.checked
                                          ? next.add("no")
                                          : next.delete("no");
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

                      {/* статус */}
                      <th>
                        <div className="col-header-with-filter">
                          <span>Статус</span>
                          <button
                            type="button"
                            className={
                              statusFilter.size
                                ? "col-filter-trigger col-filter-trigger--active"
                                : "col-filter-trigger"
                            }
                            onClick={(e) => {
                              e.stopPropagation();
                              setStatusPopup((v) => !v);
                            }}
                          >
                            ▾
                          </button>

                          {statusPopup && (
                            <div className="col-filter-popover">
                              <div className="col-filter-popover-header">
                                Фильтр по статусу
                              </div>

                              <div className="col-filter-actions">
                                <button
                                  className="col-filter-link"
                                  onClick={() =>
                                    setStatusFilter(new Set(statusOptions))
                                  }
                                >
                                  Выбрать все
                                </button>
                                <button
                                  className="col-filter-link"
                                  onClick={() => setStatusFilter(new Set())}
                                >
                                  Сбросить
                                </button>
                              </div>

                              <div className="col-filter-options">
                                {statusOptions.map((s) => (
                                  <label key={s} className="col-filter-option">
                                    <input
                                      type="checkbox"
                                      checked={statusFilter.has(s)}
                                      onChange={(e) =>
                                        setStatusFilter((old) => {
                                          const next = new Set(old);
                                          e.target.checked
                                            ? next.add(s)
                                            : next.delete(s);
                                          return next;
                                        })
                                      }
                                    />
                                    <span>{statusLabel(s)}</span>
                                  </label>
                                ))}
                              </div>
                            </div>
                          )}
                        </div>
                      </th>

                      {/* рейтинг */}
                      <th>
                        <div className="col-header-with-filter">
                          <span>Оценка</span>
                          <button
                            type="button"
                            className={
                              ratingFilter.size
                                ? "col-filter-trigger col-filter-trigger--active"
                                : "col-filter-trigger"
                            }
                            onClick={(e) => {
                              e.stopPropagation();
                              setRatingPopup((v) => !v);
                            }}
                          >
                            ▾
                          </button>

                          {ratingPopup && (
                            <div className="col-filter-popover">
                              <div className="col-filter-popover-header">
                                Фильтр по оценке
                              </div>

                              <div className="col-filter-actions">
                                <button
                                  className="col-filter-link"
                                  onClick={() =>
                                    setRatingFilter(new Set(ratingOptions))
                                  }
                                >
                                  Выбрать все
                                </button>
                                <button
                                  className="col-filter-link"
                                  onClick={() => setRatingFilter(new Set())}
                                >
                                  Сбросить
                                </button>
                              </div>

                              <div className="col-filter-options">
                                {ratingOptions.map((key) => {
                                  const num = Number(key);
                                  const label =
                                    num === 0 ? "Без оценки" : `${num} ★`;
                                  return (
                                    <label key={key} className="col-filter-option">
                                      <input
                                        type="checkbox"
                                        checked={ratingFilter.has(key)}
                                        onChange={(e) =>
                                          setRatingFilter((old) => {
                                            const next = new Set(old);
                                            e.target.checked
                                              ? next.add(key)
                                              : next.delete(key);
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
                    {paginated.length === 0 && (
                      <tr>
                        <td className="table-empty" colSpan={7}>
                          Нет категорий, подходящих под фильтр
                        </td>
                      </tr>
                    )}

                    {paginated.map((c) => (
                      <tr
                        key={c.id}
                        onClick={() => setSelectedId(c.id)}
                        className={
                          "table-row" +
                          (c.id === selectedId ? " table-row--active" : "") +
                          (c.hasUntrainedItems ? " table-row--warning" : "")
                        }
                      >
                        <td>{c.id}</td>
                        <td className="table-cell-name">{c.name}</td>
                        <td className="table-cell-description">
                          {c.description || "—"}
                        </td>
                        <td>{formatDate(c.generatedAt || c.createdAt)}</td>

                        <td>
                          {c.hasNewItems ? (
                            <span className="new-items-badge">
                              Есть новые ({c.newItemsCount || 0})
                            </span>
                          ) : (
                            <span className="new-items-badge new-items-badge--none">
                              Нет
                            </span>
                          )}

                          {c.hasUntrainedItems && (
                            <div className="training-warning">
                              Необученных СТЕ: {c.untrainedItemsCount}
                            </div>
                          )}
                        </td>

                        <td>
                          <span
                            className={`status-badge ${
                              c.status === "approved"
                                ? "status-badge--approved"
                                : c.status === "rejected"
                                ? "status-badge--rejected"
                                : "status-badge--pending"
                            }`}
                          >
                            {statusLabel(c.status)}
                          </span>
                        </td>

                        <td>
                          <StarRating
                            value={c.rating || 0}
                            onChange={(v) => updateRating(c.id, v)}
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
                      (p) => (
                        <button
                          key={p}
                          className={
                            "pagination-btn " +
                            (p === currentPage ? "pagination-btn--active" : "")
                          }
                          onClick={() => setCurrentPage(p)}
                        >
                          {p}
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

        {/* правая карточка */}
        <section className="panel-right">
          {selectedCategory ? (
            <CategoryCard
              category={selectedCategory}
              onRegenerate={regenerateCategory}
              onRatingChange={updateRating}
              onUpdate={saveCategoryPatch}
              onShowProducts={() => openProducts(selectedCategory)}
              isBusy={processing.has(selectedCategory.id)}
              onShowFamily={() => openFamily(selectedCategory)}
            />
          ) : (
            <div className="card-empty">
              Выберите категорию слева, чтобы посмотреть детали
            </div>
          )}
        </section>
      </main>

      {/* модалки */}
      {productsView && (
        <ProductsModal
          data={productsView}
          onClose={closeProducts}
          onRegenerate={regenerateCategory}
        />
      )}

      {familyView && (
        <FamilyModal data={familyView} onClose={closeFamily} />
      )}
    </div>
  );
}

// ----------------------------------
// Компонент звёздочек
// ----------------------------------
function StarRating({ value = 0, onChange }) {
  return (
    <div className="stars">
      {[1, 2, 3, 4, 5].map((n) => (
        <button
          key={n}
          type="button"
          className={`star ${value >= n ? "star--active" : ""}`}
          onClick={(e) => {
            e.stopPropagation();
            onChange?.(n);
          }}
        >
          ★
        </button>
      ))}
    </div>
  );
}

// ----------------------------------
// Карточка категории (правая панель)
// ----------------------------------
function CategoryCard({
  category,
  onRegenerate,
  onRatingChange,
  onUpdate,
  onShowProducts,
  isBusy,
  onShowFamily
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
    newItemsCount
  } = category;

  const [draft, setDraft] = useState(description || "");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setDraft(description || "");
    setSaving(false);
  }, [id, description]);

  const commit = async () => {
    const patch = { description: draft.trim() };
    try {
      setSaving(true);
      await onUpdate?.(id, patch);
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
              Сгенерировано: {formatDate(generatedAt || createdAt)}
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
              value={rating || 0}
              onChange={(v) => onRatingChange?.(id, v)}
            />
          </div>

          <div className="card-status-toggle">
            <span className="status-toggle-label">Статус:</span>

            <button
              type="button"
              className={
                "status-toggle-btn" +
                (status === "approved" ? " status-toggle-btn--active" : "")
              }
              onClick={() => onUpdate?.(id, { status: "approved" })}
            >
              Одобрено
            </button>

            <button
              type="button"
              className={
                "status-toggle-btn" +
                (status === "rejected" ? " status-toggle-btn--active" : "")
              }
              onClick={() => onUpdate?.(id, { status: "rejected" })}
            >
              Не одобрено
            </button>
          </div>

          <div className="card-actions">
            {hasNewItems && (
              <div className="card-new-items-info">
                Новые товары: {newItemsCount || 0}
              </div>
            )}

            <button
              className="btn btn-ghost btn-small"
              type="button"
              onClick={commit}
              disabled={saving}
            >
              {saving ? "Сохранение…" : "Сохранить"}
            </button>

            <button
              type="button"
              className="btn btn-ghost btn-small"
              onClick={onShowProducts}
              disabled={!productIds?.length}
            >
              Показать СТЕ
            </button>

            <button
              type="button"
              className="btn btn-ghost btn-small"
              onClick={onShowFamily}
            >
              Показать семейство
            </button>

            <button
              className="btn btn-primary"
              onClick={() => onRegenerate?.(id)}
              type="button"
              disabled={isBusy}
            >
              {isBusy ? "Перегенерация…" : "Перегенерировать"}
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
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
          />
        </div>

        <div className="card-section">
          <div className="card-section-title">Основные характеристики</div>
          {!features.length ? (
            <p className="card-section-empty">
              Для этой категории нет выделенных характеристик.
            </p>
          ) : (
            <div className="features-grid">
              {features.map((f, i) => {
                const values = Array.isArray(f.values)
                  ? f.values.join(", ")
                  : f.value || "";
                return (
                  <div key={`${f.key}-${i}`} className="feature-pill">
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
              Количество СТЕ: {productIds?.length || 0}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

// ----------------------------------
// Модалка товаров
// ----------------------------------
function ProductsModal({ data, onClose, onRegenerate }) {
  const { id, name, productIds = [], products = [], loading, error } = data;

  const [selection, setSelection] = useState(new Set(productIds));
  const [searchText, setSearchText] = useState("");

  const [producerPopup, setProducerPopup] = useState(false);
  const [countryPopup, setCountryPopup] = useState(false);

  const [producerFilter, setProducerFilter] = useState(() => new Set());
  const [countryFilter, setCountryFilter] = useState(() => new Set());

  const EMPTY_KEY = "__EMPTY__";

  const norm = (v) => {
    const t = (v || "").toString().trim();
    return t === "" ? EMPTY_KEY : t;
  };

  const labelOf = (key) => (key === EMPTY_KEY ? "пусто" : key);

  useEffect(() => {
    setSelection(new Set(productIds));
    setSearchText("");
    setProducerPopup(false);
    setCountryPopup(false);
    setProducerFilter(new Set());
    setCountryFilter(new Set());
  }, [id, productIds]);

  const producerOptions = useMemo(() => {
    const s = new Set();
    products.forEach((p) => s.add(norm(p.producer)));
    return [...s].sort((a, b) =>
      labelOf(a).localeCompare(labelOf(b), "ru", { sensitivity: "base" })
    );
  }, [products]);

  const countryOptions = useMemo(() => {
    const s = new Set();
    products.forEach((p) => s.add(norm(p.country)));
    return [...s].sort((a, b) =>
      labelOf(a).localeCompare(labelOf(b), "ru", { sensitivity: "base" })
    );
  }, [products]);

  const filtered = useMemo(() => {
    let list = products;

    const q = searchText.trim().toLowerCase();
    if (q) {
      list = list.filter((p) => {
        const block = [
          String(p.id || ""),
          p.name || "",
          p.producer || "",
          p.country || "",
          (p.raw_specs || "").toLowerCase()
        ]
          .join(" ")
          .toLowerCase();
        return block.includes(q);
      });
    }

    if (producerFilter.size) {
      list = list.filter((p) => producerFilter.has(norm(p.producer)));
    }

    if (countryFilter.size) {
      list = list.filter((p) => countryFilter.has(norm(p.country)));
    }

    return list;
  }, [products, searchText, producerFilter, countryFilter]);

  const toggle = (pid, v) => {
    setSelection((old) => {
      const next = new Set(old);
      v ? next.add(pid) : next.delete(pid);
      return next;
    });
  };

  const allChecked =
    filtered.length && filtered.every((p) => selection.has(p.id));

  const toggleAll = (v) => {
    setSelection((old) => {
      const next = new Set(old);
      if (v) filtered.forEach((p) => next.add(p.id));
      else filtered.forEach((p) => next.delete(p.id));
      return next;
    });
  };

  const doRegen = async () => {
    const ids = [...selection];
    if (!ids.length) {
      const ok = window.confirm(
        "Вы не выбрали ни одного товара. Перегенерировать по всем?"
      );
      if (!ok) return;
      await onRegenerate(id);
    } else {
      onClose();
      await onRegenerate(id, ids);
    }
  };

  const toggleFilter = (kind, key, v) => {
    const setter = kind === "producer" ? setProducerFilter : setCountryFilter;
    setter((old) => {
      const next = new Set(old);
      v ? next.add(key) : next.delete(key);
      return next;
    });
  };

  const selectAll = (kind, opts) => {
    const setter = kind === "producer" ? setProducerFilter : setCountryFilter;
    setter(new Set(opts));
  };

  const clearAll = (kind) => {
    const setter = kind === "producer" ? setProducerFilter : setCountryFilter;
    setter(new Set());
  };

  if (!data) return null;

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div
        className="modal modal-wide"
        onClick={(e) => e.stopPropagation()}
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
            <p>По указанным ID товаров ничего не найдено.</p>
          ) : (
            <>
              <div className="modal-filters">
                <div className="modal-filters-counter modal-filters-counter--top">
                  Всего: {products.length} • По фильтру: {filtered.length}
                </div>

                <div className="modal-filters-main">
                  <label className="modal-filters-label">
                    Поиск (ID, имя, производитель, страна, характеристики)
                  </label>
                  <input
                    className="input modal-filters-input"
                    placeholder="Введите текст…"
                    value={searchText}
                    onChange={(e) => setSearchText(e.target.value)}
                  />
                </div>

                <button type="button" className="btn btn-primary" onClick={doRegen}>
                  Перегенерировать
                </button>
              </div>

              <div className="products-table-wrapper">
                <table className="products-table">
                  <thead>
                    <tr>
                      <th className="products-col-checkbox">
                        <input
                          type="checkbox"
                          checked={allChecked}
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
                              producerFilter.size
                                ? "col-filter-trigger col-filter-trigger--active"
                                : "col-filter-trigger"
                            }
                            onClick={() => setProducerPopup((v) => !v)}
                          >
                            ▾
                          </button>

                          {producerPopup && (
                            <div className="col-filter-popover">
                              <div className="col-filter-popover-header">
                                Фильтр по производителю
                              </div>

                              <div className="col-filter-actions">
                                <button
                                  className="col-filter-link"
                                  onClick={() =>
                                    selectAll("producer", producerOptions)
                                  }
                                >
                                  Выбрать все
                                </button>
                                <button
                                  className="col-filter-link"
                                  onClick={() => clearAll("producer")}
                                >
                                  Сбросить
                                </button>
                              </div>

                              <div className="col-filter-options">
                                {producerOptions.map((key) => {
                                  const checked = producerFilter.has(key);
                                  return (
                                    <label key={key} className="col-filter-option">
                                      <input
                                        type="checkbox"
                                        checked={checked}
                                        onChange={(e) =>
                                          toggleFilter(
                                            "producer",
                                            key,
                                            e.target.checked
                                          )
                                        }
                                      />
                                      <span>{labelOf(key)}</span>
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
                              countryFilter.size
                                ? "col-filter-trigger col-filter-trigger--active"
                                : "col-filter-trigger"
                            }
                            onClick={() => setCountryPopup((v) => !v)}
                          >
                            ▾
                          </button>

                          {countryPopup && (
                            <div className="col-filter-popover">
                              <div className="col-filter-popover-header">
                                Фильтр по стране
                              </div>

                              <div className="col-filter-actions">
                                <button
                                  className="col-filter-link"
                                  onClick={() =>
                                    selectAll("country", countryOptions)
                                  }
                                >
                                  Выбрать все
                                </button>
                                <button
                                  className="col-filter-link"
                                  onClick={() => clearAll("country")}
                                >
                                  Сбросить
                                </button>
                              </div>

                              <div className="col-filter-options">
                                {countryOptions.map((key) => {
                                  const checked = countryFilter.has(key);
                                  return (
                                    <label key={key} className="col-filter-option">
                                      <input
                                        type="checkbox"
                                        checked={checked}
                                        onChange={(e) =>
                                          toggleFilter(
                                            "country",
                                            key,
                                            e.target.checked
                                          )
                                        }
                                      />
                                      <span>{labelOf(key)}</span>
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
                    {filtered.map((p) => (
                      <tr
                        key={p.id}
                        className={p.untrained ? "product-row--untrained" : ""}
                      >
                        <td>
                          <input
                            type="checkbox"
                            checked={selection.has(p.id)}
                            onChange={(e) => toggle(p.id, e.target.checked)}
                          />
                        </td>
                        <td>{p.id}</td>
                        <td className="products-col-name">
                          {p.name}
                          {p.untrained && (
                            <span className="product-tag-untrained">
                              UNTRAINED
                            </span>
                          )}
                        </td>
                        <td className="products-col-producer">{p.producer || "—"}</td>
                        <td className="products-col-country">{p.country || "—"}</td>
                        <td className="products-col-specs">
                          {(p.raw_specs || "")
                            .split("\n")
                            .filter(Boolean)
                            .map((line, i) => (
                              <div key={i} className="products-spec-line">
                                {line}
                              </div>
                            ))}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

// ----------------------------------
// Модалка семейства
// ----------------------------------
function FamilyModal({ data, onClose }) {
  const {
    categoryName,
    familyName,
    loading,
    error,
    members = []
  } = data || {};

  if (!data) return null;

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2 className="modal-title">Семейство категории «{categoryName}»</h2>
          <button className="btn btn-ghost btn-small" onClick={onClose}>
            ✕
          </button>
        </div>

        <div className="modal-body">
          {loading ? (
            <p>Загрузка…</p>
          ) : error ? (
            <p className="products-error">{error}</p>
          ) : (
            <>
              <p>
                <strong>Семейство:</strong> {familyName || "—"}
              </p>

              {members.length === 0 ? (
                <p className="card-section-empty">Нет членов семейства.</p>
              ) : (
                <ul className="products-list">
                  {members.map((m) => (
                    <li key={m.id} className="products-list-item">
                      <div className="products-item-header">{m.name}</div>
                      <div>ID: {m.id}</div>
                    </li>
                  ))}
                </ul>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

export default App;
