# 화면 개발 서버. compose 가 ./frontend 를 /srv 에 바인드 마운트하고
# /srv/node_modules 는 익명 볼륨으로 덮으므로, 여기서 설치한 의존성이
# 호스트 소스에 가려지지 않고 그대로 살아남는다.
FROM node:22-alpine

WORKDIR /srv

# 의존성 레이어를 소스와 분리해 소스만 바뀔 때 재설치하지 않는다
COPY package.json ./
RUN npm install

COPY . .

EXPOSE 5173

CMD ["npm", "run", "dev"]
