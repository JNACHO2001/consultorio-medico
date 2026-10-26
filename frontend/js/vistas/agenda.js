import { api, ErrorApi } from "../api.js";
import {
  abrirDialogo, alerta, areaTexto, aviso, campo, debounce, entrada, fechaLarga, h, hoyISO, horaCorta, sello, sumarDias,
} from "../ui.js";
import { vacio } from "./pacientes.js";

// Agenda de recepción: línea de tiempo del día de un médico con sus franjas libres y ocupadas.
export async function montarAgenda(raiz) {
  const medicos = await api.get("/api/medicos");
  const estado = { medicoId: medicos[0]?.id, fecha: hoyISO(), modo: "dia" };
  const zona = h("div", { "aria-live": "polite" });

  if (!medicos.length) {
    raiz.append(h("h1", {}, "Agenda y citas"), vacio("Aún no hay médicos activos. Pida al administrador que cree uno."));
    return;
  }

  const selMedico = h("select", { name: "medico", onchange: (e) => { estado.medicoId = Number(e.target.value); cargar(); } },
    medicos.map((m) => h("option", { value: m.id }, m.especialidad ? `${m.nombre_completo} · ${m.especialidad}` : m.nombre_completo)));
  const selFecha = entrada("fecha", { tipo: "date", valor: estado.fecha, onchange: (e) => { if (e.target.value) { estado.fecha = e.target.value; cargar(); } } });
  const mover = (n) => { estado.fecha = sumarDias(estado.fecha, n); selFecha.value = estado.fecha; cargar(); };
  const botonDia = h("button", { type: "button", "aria-pressed": "true", onclick: () => cambiarModo("dia") }, "Día");
  const botonSemana = h("button", { type: "button", "aria-pressed": "false", onclick: () => cambiarModo("semana") }, "Semana");
  function cambiarModo(modo) {
    estado.modo = modo;
    botonDia.setAttribute("aria-pressed", String(modo === "dia"));
    botonSemana.setAttribute("aria-pressed", String(modo === "semana"));
    cargar();
  }

  async function cargar() {
    zona.replaceChildren(h("p", { class: "cargando" }, "Cargando agenda…"));
    try {
      if (estado.modo === "dia") {
        const [citas, libres] = await Promise.all([
          api.get("/api/citas/agenda", { medico_id: estado.medicoId, fecha: estado.fecha }),
          api.get("/api/citas/horarios-libres", { medico_id: estado.medicoId, fecha: estado.fecha }),
        ]);
        zona.replaceChildren(pintarDia(citas, libres.horarios));
      } else {
        const citas = await api.get("/api/citas/agenda", { medico_id: estado.medicoId, fecha: estado.fecha, dias: 7 });
        zona.replaceChildren(pintarSemana(citas));
      }
    } catch (error) {
      zona.replaceChildren(alerta(error));
    }
  }

  function pintarDia(citas, libres) {
    const activas = citas.filter((c) => c.estado !== "CANCELADA");
    const canceladas = citas.filter((c) => c.estado === "CANCELADA");
    const porHora = new Map(activas.map((c) => [c.fecha_hora, c]));
    const horas = [...new Set([...libres, ...porHora.keys()])].sort();
    const medico = medicos.find((m) => m.id === estado.medicoId);

    const filas = horas.map((hora) => {
      const cita = porHora.get(hora);
      const contenido = cita
        ? h("button", { class: `cita ${cita.estado === "ATENDIDA" ? "atendida" : ""}`, type: "button", onclick: () => detalleCita(cita, medico) },
          h("span", { class: "quien" }, h("b", {}, cita.paciente_nombre), h("span", { class: "num" }, cita.paciente_documento)),
          sello(cita.estado))
        : h("button", { class: "libre", type: "button", onclick: () => agendar(hora, medico) }, "Disponible · agendar cita");
      return h("li", { class: `franja ${cita ? "ocupada" : ""} ${cita?.estado === "ATENDIDA" ? "atendida" : ""}` },
        h("div", { class: "hora" }, horaCorta(hora)), h("div", { class: "contenido" }, contenido));
    });

    return h("div", {},
      h("h2", { class: "titulo-dia" }, fechaLarga(estado.fecha)),
      h("p", { class: "resumen-dia" }, `${activas.length} ${activas.length === 1 ? "cita" : "citas"} · ${libres.length} ${libres.length === 1 ? "horario libre" : "horarios libres"}`),
      horas.length ? h("ol", { class: "linea-tiempo" }, filas) : vacio("No quedan horarios para este día. Pruebe con otra fecha."),
      canceladas.length
        ? h("details", { style: "margin-top:1rem" }, h("summary", {}, `Citas canceladas (${canceladas.length})`),
          h("ul", { class: "lista-simple" }, canceladas.map((c) => h("li", {},
            h("span", { class: "tachada num" }, `${horaCorta(c.fecha_hora)} · ${c.paciente_nombre}`),
            c.motivo_cancelacion ? h("div", { class: "suave pequeno" }, `Motivo: ${c.motivo_cancelacion}`) : null))))
        : null);
  }

  function pintarSemana(citas) {
    const medico = medicos.find((m) => m.id === estado.medicoId);
    const bloques = [];
    for (let i = 0; i < 7; i++) {
      const dia = sumarDias(estado.fecha, i);
      const delDia = citas.filter((c) => c.fecha_hora.startsWith(dia) && c.estado !== "CANCELADA");
      bloques.push(h("section", { class: "semana-dia panel" },
        h("h3", {}, fechaLarga(dia)),
        delDia.length
          ? h("ul", { class: "lista-simple" }, delDia.map((c) => h("li", {},
            h("button", { class: "btn-enlace btn", type: "button", onclick: () => detalleCita(c, medico) }, h("span", { class: "num" }, horaCorta(c.fecha_hora)), " · ", c.paciente_nombre),
            " ", sello(c.estado))))
          : h("p", { class: "suave" }, "Sin citas."),
        h("button", { class: "btn btn-pequeno", type: "button", onclick: () => { estado.fecha = dia; selFecha.value = dia; cambiarModo("dia"); } }, "Ver el día")));
    }
    return h("div", {}, h("p", { class: "resumen-dia" }, `Semana del ${fechaLarga(estado.fecha)}`), bloques);
  }

  // ---------------------------------------------------------------- agendar
  function agendar(hora, medico) {
    abrirDialogo({
      titulo: "Agendar cita",
      construir: (cuerpo, cerrar) => {
        let paciente = null;
        const mensaje = h("div");
        const buscador = entrada("q", { tipo: "search", placeholder: "Documento o nombre", autofocus: true });
        const resultados = h("ul", { class: "resultados" });
        const elegido = h("div");
        const confirmarBtn = h("button", { class: "btn btn-primario", type: "button", disabled: true }, "Confirmar cita");

        const buscar = debounce(async () => {
          const q = buscador.value.trim();
          if (!q) return resultados.replaceChildren();
          try {
            const lista = await api.get("/api/pacientes", { q });
            resultados.replaceChildren(...(lista.length ? lista.map((p) => h("li", {},
              h("button", { type: "button", onclick: () => elegir(p) }, h("b", {}, p.nombre_completo), h("span", { class: "num" }, `${p.tipo_documento} ${p.numero_documento}`))))
              : [h("li", { class: "suave" }, "No hay pacientes con ese dato. ", h("a", { href: "#/pacientes", onclick: cerrar }, "Registrar paciente"))]));
          } catch (error) {
            resultados.replaceChildren(alerta(error));
          }
        }, 300);
        buscador.addEventListener("input", buscar);

        function elegir(p) {
          paciente = p;
          resultados.replaceChildren();
          elegido.replaceChildren(h("div", { class: "alerta ok", style: "margin-top:.6rem" }, h("b", {}, p.nombre_completo), h("span", { class: "num" }, ` · ${p.tipo_documento} ${p.numero_documento}`)));
          confirmarBtn.disabled = false;
          confirmarBtn.focus();
        }

        confirmarBtn.addEventListener("click", async () => {
          confirmarBtn.disabled = true;
          mensaje.replaceChildren();
          try {
            await api.post("/api/citas", { paciente_id: paciente.id, medico_id: medico.id, fecha_hora: hora });
            cerrar();
            aviso(`Cita agendada para las ${horaCorta(hora)}.`);
            cargar();
          } catch (error) {
            mensaje.replaceChildren(alerta(error));
            if (error instanceof ErrorApi && error.estado === 409) cargar();
            confirmarBtn.disabled = false;
          }
        });

        cuerpo.append(
          h("p", {}, h("b", {}, medico.nombre_completo), ` · ${fechaLarga(estado.fecha)} a las `, h("b", { class: "num" }, horaCorta(hora))),
          mensaje, campo("Buscar paciente", buscador), resultados, elegido,
          h("div", { class: "acciones derecha" }, h("button", { class: "btn", type: "button", onclick: cerrar }, "Cancelar"), confirmarBtn));
      },
    });
  }

  // ---------------------------------------------------------------- ver, reprogramar y cancelar
  function detalleCita(cita, medico) {
    abrirDialogo({
      titulo: "Cita",
      construir: (cuerpo, cerrar) => {
        const pintar = (vista) => cuerpo.replaceChildren(...vista);
        const resumen = () => [
          h("dl", { class: "ficha" },
            ...[
              ["Paciente", cita.paciente_nombre],
              ["Documento", h("span", { class: "num" }, cita.paciente_documento)],
              ["Médico", medico.nombre_completo],
              ["Fecha y hora", h("span", { class: "num" }, `${fechaLarga(cita.fecha_hora.slice(0, 10))}, ${horaCorta(cita.fecha_hora)}`)],
              ["Estado", sello(cita.estado)],
            ].map(([t, v]) => h("div", {}, h("dt", {}, t), h("dd", {}, v)))),
        ];
        const inicio = () => {
          const acciones = h("div", { class: "acciones" });
          if (cita.estado === "PROGRAMADA") {
            acciones.append(
              h("button", { class: "btn btn-primario", type: "button", onclick: () => pintar(reprogramar()) }, "Reprogramar"),
              h("button", { class: "btn btn-peligro", type: "button", onclick: () => pintar(cancelar()) }, "Cancelar cita"));
          } else {
            acciones.append(h("p", { class: "suave" }, "Esta cita ya no se puede modificar."));
          }
          return [...resumen(), acciones];
        };

        const reprogramar = () => {
          const mensaje = h("div");
          const horas = h("div", { class: "cuadricula-horas" });
          const fecha = entrada("fecha", { tipo: "date", valor: cita.fecha_hora.slice(0, 10) });
          const cargarHoras = async () => {
            horas.replaceChildren(h("span", { class: "cargando" }, "Buscando horarios…"));
            try {
              const r = await api.get("/api/citas/horarios-libres", { medico_id: medico.id, fecha: fecha.value });
              horas.replaceChildren(...(r.horarios.length ? r.horarios.map((hr) => h("button", {
                type: "button",
                onclick: async () => {
                  try {
                    await api.put(`/api/citas/${cita.id}/reprogramar`, { fecha_hora: hr });
                    cerrar();
                    aviso("Cita reprogramada.");
                    estado.fecha = fecha.value;
                    selFecha.value = fecha.value;
                    cargar();
                  } catch (error) {
                    mensaje.replaceChildren(alerta(error));
                  }
                },
              }, horaCorta(hr))) : [h("span", { class: "suave" }, "No hay horarios libres ese día.")]));
            } catch (error) {
              horas.replaceChildren(alerta(error));
            }
          };
          fecha.addEventListener("change", cargarHoras);
          cargarHoras();
          return [h("p", {}, `Reprogramar la cita de ${cita.paciente_nombre}.`), mensaje, campo("Nueva fecha", fecha), horas,
            h("div", { class: "acciones" }, h("button", { class: "btn", type: "button", onclick: () => pintar(inicio()) }, "Volver"))];
        };

        const cancelar = () => {
          const motivo = areaTexto("motivo", "", { rows: 3, required: true, placeholder: "Por ejemplo: el paciente no puede asistir" });
          const mensaje = h("div");
          const boton = h("button", { class: "btn btn-peligro", type: "submit" }, "Cancelar cita");
          const form = h("form", {
            onsubmit: async (e) => {
              e.preventDefault();
              boton.disabled = true;
              try {
                await api.post(`/api/citas/${cita.id}/cancelar`, { motivo: motivo.value.trim() });
                cerrar();
                aviso("Cita cancelada. El horario quedó libre.");
                cargar();
              } catch (error) {
                mensaje.replaceChildren(alerta(error));
                boton.disabled = false;
              }
            },
          }, mensaje, campo("Motivo de la cancelación", motivo),
            h("div", { class: "acciones" }, boton, h("button", { class: "btn", type: "button", onclick: () => pintar(inicio()) }, "Volver")));
          return [form];
        };
        pintar(inicio());
      },
    });
  }

  raiz.append(
    h("header", { class: "encabezado" }, h("div", {}, h("h1", {}, "Agenda y citas"), h("p", {}, "Elija un médico y un día. Toque un horario libre para agendar."))),
    h("div", { class: "panel" },
      h("div", { class: "barra" },
        campo("Médico", selMedico),
        h("div", { class: "dia-nav" },
          h("button", { class: "btn", type: "button", "aria-label": "Día anterior", onclick: () => mover(estado.modo === "dia" ? -1 : -7) }, "‹"),
          campo("Fecha", selFecha),
          h("button", { class: "btn", type: "button", "aria-label": "Día siguiente", onclick: () => mover(estado.modo === "dia" ? 1 : 7) }, "›"),
          h("button", { class: "btn", type: "button", onclick: () => { estado.fecha = hoyISO(); selFecha.value = estado.fecha; cargar(); } }, "Hoy")),
        h("div", { class: "segmento", role: "group", "aria-label": "Vista" }, botonDia, botonSemana)),
      zona));
  await cargar();
}
