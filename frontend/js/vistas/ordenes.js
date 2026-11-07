import { api } from "../api.js";
import {
  abrirDialogo, alerta, anexar, areaTexto, aviso, AREAS_APOYO, campo, entrada, fechaHora, h, sello,
} from "../ui.js";
import { vacio } from "./pacientes.js";

// Parámetros habituales por examen: ahorran digitar. Los rangos son de adulto y se pueden cambiar.
const PLANTILLAS = {
  "LAB-HEM": [
    ["Hemoglobina", "g/dL", 12, 17.5], ["Hematocrito", "%", 36, 52],
    ["Leucocitos", "/µL", 4500, 11000], ["Plaquetas", "/µL", 150000, 450000],
  ],
  "LAB-GLU": [["Glucosa en ayunas", "mg/dL", 70, 99]],
  "LAB-ORI": [["Color", "", null, null], ["Aspecto", "", null, null], ["Densidad", "", 1.005, 1.03], ["pH", "", 4.5, 8]],
  "ECG-001": [["Frecuencia cardíaca", "lpm", 60, 100], ["Intervalo PR", "ms", 120, 200], ["QRS", "ms", 80, 120], ["QTc", "ms", 350, 450]],
};

export const sinPrioridad = (o) => (o.prioridad === "URGENTE" ? h("span", { class: "sello anulada" }, "Urgente") : null);

// Resultado de una orden (solo lectura).
export function abrirResultado(orden) {
  abrirDialogo({
    titulo: `${orden.nombre}`,
    ancho: true,
    construir: (cuerpo) => {
      anexar(cuerpo, [
        h("dl", { class: "ficha" },
          dato("Paciente", `${orden.paciente_nombre} · ${orden.paciente_documento}`), dato("Médico que ordena", orden.medico_nombre),
          dato("Ordenado", fechaHora(orden.fecha)), dato("Área", AREAS_APOYO[orden.area]),
          orden.fecha_resultado ? dato("Resultado registrado", `${fechaHora(orden.fecha_resultado)} · ${orden.registrado_por}`) : null,
          orden.indicacion ? dato("Indicación clínica", orden.indicacion) : null),
        orden.estado === "ANULADA" ? h("div", { class: "alerta" }, h("b", {}, "Orden anulada. "), orden.motivo_anulacion) : null,
        orden.estado === "SOLICITADA" ? h("div", { class: "alerta info" }, "Todavía no tiene resultado.") : null,
        orden.valores.length
          ? h("div", { class: "tabla-contenedor" }, h("table", {},
            h("thead", {}, h("tr", {}, ["Parámetro", "Resultado", "Unidad", "Referencia", ""].map((t, i) => h("th", { class: i === 1 ? "num" : "" }, t)))),
            h("tbody", {}, orden.valores.map((v) => h("tr", { class: v.alterado ? "alterado" : "" },
              h("td", {}, v.parametro), h("td", { class: "num" }, h("b", {}, v.valor)), h("td", {}, v.unidad || ""),
              h("td", { class: "num suave" }, rango(v)),
              h("td", {}, v.alterado ? h("span", { class: "sello anulada" }, "Fuera de rango") : null))))))
          : null,
        orden.interpretacion ? h("div", { class: "nota" }, h("small", {}, "Interpretación"), orden.interpretacion) : null,
      ]);
    },
  });
}

function dato(t, v) {
  return h("div", {}, h("dt", {}, t), h("dd", {}, v || "—"));
}

function rango(v) {
  if (v.ref_min == null && v.ref_max == null) return "—";
  if (v.ref_min == null) return `≤ ${v.ref_max}`;
  if (v.ref_max == null) return `≥ ${v.ref_min}`;
  return `${v.ref_min} – ${v.ref_max}`;
}

// Formulario de resultado (apoyo diagnóstico).
export function formResultado(orden, alGuardar) {
  abrirDialogo({
    titulo: `Resultado: ${orden.nombre}`,
    ancho: true,
    construir: (cuerpo, cerrar) => {
      const mensaje = h("div");
      const filas = h("tbody");
      const numero = (v) => (v === "" || v == null ? null : Number(String(v).replace(",", ".")));
      const fila = (parametro = "", unidad = "", min = null, max = null) => {
        const f = h("tr", {},
          h("td", {}, entrada("parametro", { valor: parametro, "aria-label": "Parámetro", maxlength: 80 })),
          h("td", {}, entrada("valor", { "aria-label": "Valor", maxlength: 60 })),
          h("td", {}, entrada("unidad", { valor: unidad, "aria-label": "Unidad", maxlength: 20 })),
          h("td", {}, entrada("ref_min", { valor: min ?? "", "aria-label": "Mínimo", inputmode: "decimal" })),
          h("td", {}, entrada("ref_max", { valor: max ?? "", "aria-label": "Máximo", inputmode: "decimal" })),
          h("td", {}, h("button", { class: "btn btn-pequeno btn-peligro", type: "button", "aria-label": "Quitar línea", onclick: () => f.remove() }, "×")));
        filas.append(f);
      };
      (PLANTILLAS[orden.codigo] || [["", "", null, null]]).forEach((p) => fila(...p));
      const guardar = h("button", { class: "btn btn-primario", type: "submit" }, "Guardar resultado");
      const interpretacion = areaTexto("interpretacion", "", { rows: 3, maxlength: 3000 });
      const form = h("form", {
        onsubmit: async (e) => {
          e.preventDefault();
          guardar.disabled = true;
          const valores = [...filas.children].map((f) => {
            const v = (n) => f.querySelector(`[name=${n}]`).value.trim();
            return { parametro: v("parametro"), valor: v("valor"), unidad: v("unidad"), ref_min: numero(v("ref_min")), ref_max: numero(v("ref_max")) };
          }).filter((v) => v.valor || v.parametro);
          try {
            const hecha = await api.post(`/api/ordenes/${orden.id}/resultado`, { valores, interpretacion: interpretacion.value.trim() });
            cerrar();
            aviso("Resultado registrado y cargado a la cuenta del paciente.");
            alGuardar(hecha);
          } catch (error) {
            mensaje.replaceChildren(alerta(error));
            guardar.disabled = false;
          }
        },
      }, mensaje,
        h("p", {}, h("b", {}, orden.paciente_nombre), ` · ${orden.paciente_documento}`, orden.indicacion ? h("span", { class: "suave" }, ` · ${orden.indicacion}`) : null),
        h("div", { class: "tabla-contenedor" }, h("table", { class: "resultado-edicion" },
          h("thead", {}, h("tr", {}, ["Parámetro", "Valor", "Unidad", "Ref. mín.", "Ref. máx.", ""].map((t) => h("th", {}, t)))), filas)),
        h("button", { class: "btn btn-pequeno", type: "button", style: "margin:.5rem 0 1rem", onclick: () => fila() }, "Agregar línea"),
        campo("Interpretación", interpretacion, "Opcional si registró valores. Al guardar, el servicio se cobra en la cuenta del ingreso."),
        h("div", { class: "acciones derecha" }, h("button", { class: "btn", type: "button", onclick: cerrar }, "Cancelar"), guardar));
      cuerpo.append(form);
    },
  });
}

// Tabla de órdenes. `acciones(orden)` devuelve los botones de cada fila.
export function tablaOrdenes(ordenes, { mostrarPaciente = false, acciones = () => [] } = {}) {
  if (!ordenes.length) return vacio("No hay órdenes.");
  return h("div", { class: "tabla-contenedor" }, h("table", {},
    h("thead", {}, h("tr", {}, [mostrarPaciente ? "Paciente" : null, "Examen", "Área", "Fecha", "Estado", ""].filter((t) => t !== null).map((t) => h("th", {}, t)))),
    h("tbody", {}, ordenes.map((o) => h("tr", {},
      mostrarPaciente ? h("td", {}, h("b", {}, o.paciente_nombre), h("div", { class: "suave pequeno num" }, o.paciente_documento)) : null,
      h("td", {}, h("b", {}, o.nombre), o.cantidad > 1 ? ` × ${o.cantidad}` : "", " ", sinPrioridad(o),
        o.indicacion ? h("div", { class: "suave pequeno" }, o.indicacion) : null),
      h("td", {}, AREAS_APOYO[o.area]), h("td", { class: "fecha" }, fechaHora(o.fecha)),
      h("td", {}, sello(o.estado), o.alterada ? h("div", {}, h("span", { class: "sello anulada" }, "Alterado")) : null),
      h("td", {}, h("div", { class: "celda-acciones" }, acciones(o))))))));
}
