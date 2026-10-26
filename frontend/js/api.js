// Cliente de la API REST. Es la única capa del frontend que conoce las rutas del servidor.
const CLAVE = "consultorio.sesion";

export const sesion = {
  leer() {
    try {
      return JSON.parse(sessionStorage.getItem(CLAVE));
    } catch {
      return null;
    }
  },
  guardar(valor) {
    try {
      sessionStorage.setItem(CLAVE, JSON.stringify(valor));
    } catch {
      /* sin almacenamiento: la sesión vive solo en memoria */
    }
    memoria = valor;
  },
  borrar() {
    try {
      sessionStorage.removeItem(CLAVE);
    } catch {
      /* nada que borrar */
    }
    memoria = null;
  },
  actual() {
    return memoria ?? this.leer();
  },
};
let memoria = null;

export class ErrorApi extends Error {
  constructor(estado, cuerpo) {
    super(cuerpo?.detail || "Ocurrió un error inesperado.");
    this.estado = estado;
    this.cuerpo = cuerpo || {};
  }
}

let alExpirar = () => {};
export function cuandoExpireLaSesion(funcion) {
  alExpirar = funcion;
}

async function pedir(metodo, ruta, { cuerpo, params } = {}) {
  const url = new URL(ruta, window.location.origin);
  for (const [clave, valor] of Object.entries(params || {})) {
    if (valor !== "" && valor != null) url.searchParams.set(clave, valor);
  }
  const actual = sesion.actual();
  const cabeceras = {};
  if (cuerpo !== undefined) cabeceras["Content-Type"] = "application/json";
  if (actual) cabeceras.Authorization = `Bearer ${actual.token}`;

  let respuesta;
  try {
    respuesta = await fetch(url, {
      method: metodo,
      headers: cabeceras,
      body: cuerpo !== undefined ? JSON.stringify(cuerpo) : undefined,
    });
  } catch {
    throw new ErrorApi(0, { detail: "No hay conexión con el servidor. Revise la red e intente de nuevo." });
  }
  if (respuesta.status === 204) return null;

  let datos = null;
  try {
    datos = await respuesta.json();
  } catch {
    /* respuesta sin cuerpo JSON */
  }
  if (!respuesta.ok) {
    if (respuesta.status === 401 && actual && !ruta.endsWith("/login")) alExpirar();
    throw new ErrorApi(respuesta.status, datos || { detail: "El servidor no pudo completar la solicitud." });
  }
  return datos;
}

export const api = {
  get: (ruta, params) => pedir("GET", ruta, { params }),
  post: (ruta, cuerpo) => pedir("POST", ruta, { cuerpo }),
  put: (ruta, cuerpo) => pedir("PUT", ruta, { cuerpo }),
};

export async function iniciarSesion(usuario, contrasena) {
  const datos = await api.post("/api/auth/login", { usuario, contrasena });
  sesion.guardar({ token: datos.access_token, usuario: datos.usuario });
  return datos.usuario;
}

export async function cerrarSesion() {
  try {
    await api.post("/api/auth/logout");
  } catch {
    /* si el token ya no sirve, igual se cierra la sesión local */
  }
  sesion.borrar();
}
