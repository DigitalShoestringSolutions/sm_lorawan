
FROM redis:7-alpine

CMD ["redis-server","--save","", "--appendonly", "no" ,"--maxmemory", "32mb", "--maxmemory-policy", "volatile-lru"]
