// Utilidades de interfaz: construcción segura del DOM, avisos, diálogos y formatos.
// Todo el texto que viene del servidor se inserta con textContent (nunca innerHTML) para evitar XSS.

export function h(etiqueta, atributos, ...hijos) {
  const el = document.createElement(etiqueta);
  for (const [clave, valor] of Object.entries(atributos || {})) {
    if (valor == null || valor === false) continue;
    if (clave === "class") el.className = valor;
    else if (clave.startsWith("on") && typeof valor === "function") el.addEventListener(clave.slice(2), valor);
    else if (valor === true) el.setAttribute(clave, "");
    else el.setAttribute(clave, valor);
  }
  anexar(el, hijos);
  return el;
}

export function anexar(el, hijos) {
  for (const hijo of hijos.flat(Infinity)) {
    if (hijo == null || hijo === false) continue;
    el.append(hijo instanceof Node ? hijo : document.createTextNode(String(hijo)));
  }
  return el;
}

// ------------------------------------------------------------------ fechas (zona del consultorio)
const ZONA = "America/Bogota";

export const hoyISO = () => new Intl.DateTimeFormat("en-CA", { timeZone: ZONA }).format(new Date());

export function sumarDias(iso, n) {
  const [a, m, d] = iso.split("-").map(Number);
  return new Date(Date.UTC(a, m - 1, d + n)).toISOString().slice(0, 10);
}

export function fechaLarga(iso) {
  return new Date(`${iso}T12:00:00Z`).toLocaleDateString("es-CO", {
    weekday: "long", day: "numeric", month: "long", year: "numeric", timeZone: "UTC",
  }).replace(/ de /g, " de ");
}

export const horaCorta = (isoFechaHora) => isoFechaHora.slice(11, 16);
export const soloFecha = (iso) => (iso ? `${iso.slice(8, 10)}/${iso.slice(5, 7)}/${iso.slice(0, 4)}` : "—");
export const fechaHora = (iso) => `${soloFecha(iso)} ${horaCorta(iso)}`;

export function edad(fechaNacimiento) {
  if (!fechaNacimiento) return "";
  const [a, m, d] = fechaNacimiento.split("-").map(Number);
  const [ha, hm, hd] = hoyISO().split("-").map(Number);
  let anos = ha - a;
  if (hm < m || (hm === m && hd < d)) anos -= 1;
  return `${anos} años`;
}

export const ROLES = { RECEPCION: "Recepción", MEDICO: "Médico", ADMINISTRADOR: "Administrador" };
export const ESTADOS = { PROGRAMADA: "Programada", ATENDIDA: "Atendida", CANCELADA: "Cancelada" };

export const sello = (estado) => h("span", { class: `sello ${estado.toLowerCase()}` }, ESTADOS[estado] || estado);

// ------------------------------------------------------------------ avisos
export function aviso(texto, tipo = "ok") {
  const contenedor = document.getElementById("avisos");
  const el = h("div", { class: `aviso ${tipo === "error" ? "error" : ""}` }, texto);
  contenedor.append(el);
  setTimeout(() => el.remove(), tipo === "error" ? 7000 : 3800);
}

export function alerta(error, tipo = "") {
  const texto = typeof error === "string" ? error : error?.message || "Ocurrió un error inesperado.";
  return h("div", { class: `alerta ${tipo}`, role: "alert" }, texto);
}

// ------------------------------------------------------------------ diálogos
export function abrirDialogo({ titulo, ancho = false, construir }) {
  const dialogo = h("dialog", { class: ancho ? "ancho" : "", "aria-labelledby": "dialogo-titulo" });
  const cuerpo = h("div", { class: "dialogo-cuerpo" });
  const cerrar = () => {
    dialogo.close();
    dialogo.remove();
  };
  dialogo.append(
    h("div", { class: "dialogo-cabecera" },
      h("h2", { id: "dialogo-titulo" }, titulo),
      h("button", { class: "cerrar", type: "button", "aria-label": "Cerrar", onclick: cerrar }, "×")),
    cuerpo
  );
  dialogo.addEventListener("close", () => dialogo.remove());
  document.body.append(dialogo);
  construir(cuerpo, cerrar);
  dialogo.showModal();
  return { cerrar, cuerpo };
}

export function confirmar({ titulo, mensaje, textoConfirmar = "Confirmar", peligro = false }) {
  return new Promise((resolver) => {
    let decidido = false;
    const decidir = (valor, cerrar) => {
      decidido = true;
      cerrar();
      resolver(valor);
    };
    const { cuerpo } = abrirDialogo({
      titulo,
      construir: (c, cerrar) => {
        c.append(
          h("p", {}, mensaje),
          h("div", { class: "acciones derecha" },
            h("button", { class: "btn", type: "button", onclick: () => decidir(false, cerrar) }, "Volver"),
            h("button", { class: `btn ${peligro ? "btn-peligro" : "btn-primario"}`, type: "button", onclick: () => decidir(true, cerrar) }, textoConfirmar))
        );
      },
    });
    cuerpo.closest("dialog").addEventListener("close", () => {
      if (!decidido) resolver(false);
    });
  });
}

// ------------------------------------------------------------------ formularios
export function campo(etiqueta, control, ayuda) {
  return h("label", { class: "campo" }, h("span", {}, etiqueta), control, ayuda ? h("small", {}, ayuda) : null);
}

export function entrada(nombre, { tipo = "text", valor = "", requerido = false, ...resto } = {}) {
  return h("input", { name: nombre, type: tipo, value: valor ?? "", required: requerido, autocomplete: "off", ...resto });
}

export function areaTexto(nombre, valor = "", resto = {}) {
  const area = h("textarea", { name: nombre, ...resto });
  area.value = valor ?? "";
  return area;
}

export function seleccion(nombre, opciones, valor = "") {
  const el = h("select", { name: nombre },
    opciones.map(([v, texto]) => h("option", { value: v }, texto)));
  el.value = valor;
  return el;
}

export function datosDe(formulario) {
  const datos = {};
  for (const [clave, valor] of new FormData(formulario).entries()) datos[clave] = String(valor).trim();
  return datos;
}

export function ocupado(boton, fn) {
  return async (...args) => {
    boton.disabled = true;
    try {
      return await fn(...args);
    } finally {
      boton.disabled = false;
    }
  };
}

export function debounce(fn, ms = 300) {
  let t;
  return (...args) => {
    clearTimeout(t);
    t = setTimeout(() => fn(...args), ms);
  };
}
