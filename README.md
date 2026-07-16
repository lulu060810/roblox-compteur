<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<title>Steal a Legend - Joueurs en ligne</title>

<style>
body {
    margin: 0;
    font-family: Arial, sans-serif;
    background: transparent;
}

.box {
    text-align: center;
    padding: 20px;
    border-radius: 15px;
    background: #111827;
    color: white;
    font-size: 22px;
}

.number {
    font-size: 45px;
    font-weight: bold;
}
</style>
</head>

<body>

<div class="box">
    👥 Joueurs en ligne<br>
    <span class="number" id="players">...</span>
</div>

<script>
const PLACE_ID = "136916300164987";

async function updatePlayers() {
    try {
        const universe = await fetch(
            `https://apis.roblox.com/universes/v1/places/${PLACE_ID}/universe`
        ).then(r => r.json());

        const game = await fetch(
            `https://games.roblox.com/v1/games?universeIds=${universe.universeId}`
        ).then(r => r.json());

        document.getElementById("players").innerHTML =
            game.data[0].playing;

    } catch(e) {
        document.getElementById("players").innerHTML =
            "Erreur";
    }
}

updatePlayers();
setInterval(updatePlayers, 30000);
</script>

</body>
</html>
