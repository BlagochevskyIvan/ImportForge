import Link from "next/link";

export default function Home() {
  return <main id="main" className="container">
    <section className="hero">
      <div>
        <p className="eyebrow"><span className="dot" /> Рабочее пространство поставщиков</p>
        <h1>Порядок в данных.<br />С самого начала.</h1>
        <p className="lead">Соберите поставщиков в одном месте. Названия, контакты и статусы — всё под рукой, чтобы подготовиться к регулярному импорту данных.</p>
        <div className="actions">
          <Link href="/register" className="button">Зарегистрироваться <span aria-hidden="true">↗</span></Link>
          <Link href="/login" className="button secondary">Войти</Link>
        </div>
        <p className="small-text hero-note">Ваш аккаунт. Ваши поставщики. Единое пространство.</p>
      </div>
      <div className="flow" aria-label="Схема работы с поставщиками">
        <div className="flow-top"><span>IMPORTFORGE / WORKSPACE</span><span aria-hidden="true">01 — 03</span></div>
        <div className="flow-file"><span className="file-icon" aria-hidden="true">01</span><div><strong>Создайте аккаунт</strong><p className="small-text">Личный доступ к рабочему пространству</p></div></div>
        <div className="flow-arrow" aria-hidden="true">↓</div>
        <div className="flow-file"><span className="file-icon" aria-hidden="true">02</span><div><strong>Добавьте поставщика</strong><p className="small-text">Название и контактный email</p></div></div>
        <div className="flow-arrow" aria-hidden="true">↓</div>
        <div className="flow-result"><strong>База для будущих импортов</strong><p className="small-text">Контакты и статусы в одном списке</p></div>
      </div>
    </section>
    <section className="features" aria-label="Возможности">
      <article><span className="feature-number">01 / ПРОСТОЙ СТАРТ</span><h3>От аккаунта к работе</h3><p>Зарегистрируйтесь и создайте первого поставщика за несколько шагов.</p></article>
      <article><span className="feature-number">02 / ЕДИНЫЙ СПИСОК</span><h3>Контакты в порядке</h3><p>Просматривайте поставщиков, их email и текущий статус в личном кабинете.</p></article>
      <article><span className="feature-number">03 / ЛИЧНЫЙ ДОСТУП</span><h3>Свои данные под рукой</h3><p>Каждый аккаунт работает со своим списком поставщиков.</p></article>
    </section>
  </main>;
}
