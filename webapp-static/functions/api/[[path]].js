export async function onRequest(context) {
  const url = new URL(context.request.url);
  
  // Определяем путь, который нужно проксировать (убираем /api из начала)
  const proxyPath = url.pathname.replace(/^\/api/, '');
  
  // Ваш IP сервера
  const BACKEND_URL = 'http://84.245.120.116:8000';
  
  // Формируем новый URL для запроса к вашему серверу
  const targetUrl = `${BACKEND_URL}${proxyPath}${url.search}`;
  
  // Клонируем оригинальный запрос, но меняем URL
  const modifiedRequest = new Request(targetUrl, {
    method: context.request.method,
    headers: context.request.headers,
    body: context.request.body,
    redirect: 'follow'
  });

  try {
    const response = await fetch(modifiedRequest);
    
    // Создаем новый ответ, чтобы добавить CORS заголовки (на всякий случай)
    const newResponse = new Response(response.body, response);
    newResponse.headers.set('Access-Control-Allow-Origin', '*');
    
    return newResponse;
  } catch (e) {
    return new Response(`Proxy Error: ${e.message}`, { status: 500 });
  }
}
