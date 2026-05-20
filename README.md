# Smart Factory Dashboard

## Docker 실행

Docker Desktop이 실행 중이면 프로젝트 루트에서 한 번에 프론트엔드, 백엔드, Postgres를 실행할 수 있습니다.

```bash
docker compose up -d
```

실행 후 접속 주소:

- Frontend: http://localhost:5173
- Backend API: http://localhost:8000
- Backend health: http://localhost:8000/health

`backend/.env` 또는 루트 `.env`가 있으면 API 컨테이너가 선택적으로 읽습니다. 파일이 없어도 기본 템플릿 설정으로 실행됩니다.

이미지를 강제로 다시 만들고 싶을 때만 아래 명령을 사용하면 됩니다.

```bash
docker compose up -d --build
```

## 로컬 개발 실행

프론트엔드를 Vite 개발 서버로 직접 실행할 수도 있습니다.

```bash
npm install
npm run dev
```

프론트엔드는 기본적으로 `http://127.0.0.1:8000` 백엔드 API를 사용합니다. 다른 주소를 쓰려면 `VITE_API_BASE_URL`을 설정하세요.

```bash
VITE_API_BASE_URL=http://127.0.0.1:8000
```

## 자주 쓰는 명령

```bash
npm run build
docker compose ps
docker compose logs -f api
docker compose down
```

export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      // Other configs...
      // Enable lint rules for React
      reactX.configs['recommended-typescript'],
      // Enable lint rules for React DOM
      reactDom.configs.recommended,
    ],
    languageOptions: {
      parserOptions: {
        project: ['./tsconfig.node.json', './tsconfig.app.json'],
        tsconfigRootDir: import.meta.dirname,
      },
      // other options...
    },
  },
])
```
