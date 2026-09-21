# Board map — seed 507

Start: **node:35** (`settlement:3` / Settlement 2-1)
Topology: 19 hexes / 54 nodes / 72 edges

## Settlements
- `settlement:1` @ `node:2` (faction:1) Settlement 1-1
- `settlement:2` @ `node:12` (faction:1) Settlement 1-2
- `settlement:3` @ `node:35` (faction:2) Settlement 2-1 ← John starts here
- `settlement:4` @ `node:27` (faction:2) Settlement 2-2

## Constructed roads
- `node:2` ↔ `node:5` (faction:1)
- `node:12` ↔ `node:17` (faction:1)
- `node:35` ↔ `node:29` (faction:2)
- `node:27` ↔ `node:21` (faction:2)

## Hexes (terrain + number token)
- `hex:-1,-1` terrain=`desert` number=`10`
- `hex:-1,0` terrain=`desert` number=`9`
- `hex:-1,1` terrain=`ore_mountains` number=`12`
- `hex:-1,2` terrain=`fields` number=`11`
- `hex:-2,0` terrain=`fields` number=`8`
- `hex:-2,1` terrain=`grazing_land` number=`6`
- `hex:-2,2` terrain=`grazing_land` number=`9`
- `hex:0,-1` terrain=`fields` number=`5`
- `hex:0,-2` terrain=`woodland` number=`6`
- `hex:0,0` terrain=`clay_mountains` number=`8`
- `hex:0,1` terrain=`clay_mountains` number=`4`
- `hex:0,2` terrain=`clay_mountains` number=`2`
- `hex:1,-1` terrain=`grazing_land` number=`9`
- `hex:1,-2` terrain=`fields` number=`10`
- `hex:1,0` terrain=`woodland` number=`4`
- `hex:1,1` terrain=`ore_mountains` number=`11`
- `hex:2,-1` terrain=`woodland` number=`5`
- `hex:2,-2` terrain=`ore_mountains` number=`3`
- `hex:2,0` terrain=`woodland` number=`3`

## Nodes (★ settlement, ↕ road endpoint)
- `node:1` [wilderness] → `node:4`, `node:5`
- `node:2` [★SETTLEMENT ↕ROAD] → `node:5`, `node:6`
- `node:3` [wilderness] → `node:6`, `node:7`
- `node:4` [wilderness] → `node:1`, `node:8`
- `node:5` [↕ROAD] → `node:1`, `node:2`, `node:9`
- `node:6` [wilderness] → `node:2`, `node:3`, `node:10`
- `node:7` [wilderness] → `node:3`, `node:11`
- `node:8` [wilderness] → `node:4`, `node:12`, `node:13`
- `node:9` [wilderness] → `node:5`, `node:13`, `node:14`
- `node:10` [wilderness] → `node:6`, `node:14`, `node:15`
- `node:11` [wilderness] → `node:7`, `node:15`, `node:16`
- `node:12` [★SETTLEMENT ↕ROAD] → `node:8`, `node:17`
- `node:13` [wilderness] → `node:8`, `node:9`, `node:18`
- `node:14` [wilderness] → `node:9`, `node:10`, `node:19`
- `node:15` [wilderness] → `node:10`, `node:11`, `node:20`
- `node:16` [wilderness] → `node:11`, `node:21`
- `node:17` [↕ROAD] → `node:12`, `node:22`, `node:23`
- `node:18` [wilderness] → `node:13`, `node:23`, `node:24`
- `node:19` [wilderness] → `node:14`, `node:24`, `node:25`
- `node:20` [wilderness] → `node:15`, `node:25`, `node:26`
- `node:21` [↕ROAD] → `node:16`, `node:26`, `node:27`
- `node:22` [wilderness] → `node:17`, `node:28`
- `node:23` [wilderness] → `node:17`, `node:18`, `node:29`
- `node:24` [wilderness] → `node:18`, `node:19`, `node:30`
- `node:25` [wilderness] → `node:19`, `node:20`, `node:31`
- `node:26` [wilderness] → `node:20`, `node:21`, `node:32`
- `node:27` [★SETTLEMENT ↕ROAD] → `node:21`, `node:33`
- `node:28` [wilderness] → `node:22`, `node:34`
- `node:29` [↕ROAD] → `node:23`, `node:34`, `node:35`
- `node:30` [wilderness] → `node:24`, `node:35`, `node:36`
- `node:31` [wilderness] → `node:25`, `node:36`, `node:37`
- `node:32` [wilderness] → `node:26`, `node:37`, `node:38`
- `node:33` [wilderness] → `node:27`, `node:38`
- `node:34` [wilderness] → `node:28`, `node:29`, `node:39`
- `node:35` [★SETTLEMENT ↕ROAD] → `node:29`, `node:30`, `node:40`
- `node:36` [wilderness] → `node:30`, `node:31`, `node:41`
- `node:37` [wilderness] → `node:31`, `node:32`, `node:42`
- `node:38` [wilderness] → `node:32`, `node:33`, `node:43`
- `node:39` [wilderness] → `node:34`, `node:44`
- `node:40` [wilderness] → `node:35`, `node:44`, `node:45`
- `node:41` [wilderness] → `node:36`, `node:45`, `node:46`
- `node:42` [wilderness] → `node:37`, `node:46`, `node:47`
- `node:43` [wilderness] → `node:38`, `node:47`
- `node:44` [wilderness] → `node:39`, `node:40`, `node:48`
- `node:45` [wilderness] → `node:40`, `node:41`, `node:49`
- `node:46` [wilderness] → `node:41`, `node:42`, `node:50`
- `node:47` [wilderness] → `node:42`, `node:43`, `node:51`
- `node:48` [wilderness] → `node:44`, `node:52`
- `node:49` [wilderness] → `node:45`, `node:52`, `node:53`
- `node:50` [wilderness] → `node:46`, `node:53`, `node:54`
- `node:51` [wilderness] → `node:47`, `node:54`
- `node:52` [wilderness] → `node:48`, `node:49`
- `node:53` [wilderness] → `node:49`, `node:50`
- `node:54` [wilderness] → `node:50`, `node:51`
