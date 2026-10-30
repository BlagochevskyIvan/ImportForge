import Link from "next/link";
import type { Supplier } from "@/lib/api";

export default function SupplierList({ suppliers }: { suppliers: Supplier[] }) {
  if (!suppliers.length) return <div className="empty"><h3>Добавьте первого поставщика</h3><p className="muted">Создайте карточку с названием и контактным email.</p></div>;
  return <div className="table-wrap" role="region" aria-label="Список поставщиков, таблица с горизонтальной прокруткой" tabIndex={0}>
    <table aria-label="Ваши поставщики">
      <thead><tr><th scope="col">Поставщик</th><th scope="col">Контактный email</th><th scope="col">Статус</th><th scope="col">Действие</th></tr></thead>
      <tbody>{suppliers.map((supplier) => <tr key={supplier.id}>
        <td><Link href={`/suppliers/${supplier.id}`}><strong>{supplier.name}</strong></Link><div className="small-text">ID {supplier.id}</div></td>
        <td>{supplier.contact_email}</td>
        <td><span className={`badge${supplier.is_active ? "" : " inactive"}`}>{supplier.is_active ? "Активен" : "Неактивен"}</span></td>
        <td><Link className="button secondary small" href={`/suppliers/${supplier.id}`} aria-label={`Выбрать поставщика ${supplier.name}`}>Выбрать →</Link></td>
      </tr>)}</tbody>
    </table>
  </div>;
}
