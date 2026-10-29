import type { Supplier } from "@/lib/api";

export default function SupplierList({ suppliers }: { suppliers: Supplier[] }) {
  if (!suppliers.length) return <div className="empty"><h3>Добавьте первого поставщика</h3><p className="muted">Создайте карточку с названием и контактным email.</p></div>;
  return <div className="table-wrap" role="region" aria-label="Список поставщиков, таблица с горизонтальной прокруткой" tabIndex={0}>
    <table aria-label="Ваши поставщики">
      <thead><tr><th scope="col">Поставщик</th><th scope="col">Контактный email</th><th scope="col">Статус</th></tr></thead>
      <tbody>{suppliers.map((supplier) => <tr key={supplier.id}>
        <td><strong>{supplier.name}</strong><div className="small-text">ID {supplier.id}</div></td>
        <td>{supplier.contact_email}</td>
        <td><span className={`badge${supplier.is_active ? "" : " inactive"}`}>{supplier.is_active ? "Активен" : "Неактивен"}</span></td>
      </tr>)}</tbody>
    </table>
  </div>;
}
