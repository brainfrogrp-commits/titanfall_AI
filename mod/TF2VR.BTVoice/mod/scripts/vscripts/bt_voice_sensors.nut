global function BTVoice_Init

// Sends game information to the BT-7274 voice companion app (a small web server
// on this PC). Each sensor runs in its own thread, so if one of them hits a
// script error the others keep working, and the app reports which one failed.

const string BTVOICE_URL = "http://127.0.0.1:5757/api/event"
const float BTVOICE_TICK = 1.5
const float BTVOICE_MIN_GAP = 3.0       // fewest seconds between "something changed" messages
const float BTVOICE_HEARTBEAT = 15.0    // send at least this often, so the app knows we are alive
const float BTVOICE_COVER_RANGE = 600.0 // units (about 15 m): solid overhead closer than this counts as cover
const float BTVOICE_ENEMY_RANGE = 2400.0
const float BTVOICE_SENSOR_STALE = 6.0
const int BTVOICE_LOW_HEALTH = 30

struct
{
	entity player
	bool haveBaseline = false
	bool wasTitan = false
	bool wasLow = false
	bool wasAlive = true
	string lastSignature = ""
	float lastSend = 0.0

	// latest readings, each written by its own sensor thread
	string location = "outdoors"
	bool inTitan = false
	int healthPct = -1
	int btDistance = -1
	int btHealthPct = -1
	string weapon = ""
	int enemies = 0
	int enemyTitans = 0
	bool onGround = true
	bool sliding = false
	bool crouched = false
	bool wallRunning = false

	// when each sensor last finished without an error
	float okLocation = 0.0
	float okTitan = 0.0
	float okHealth = 0.0
	float okBT = 0.0
	float okWeapon = 0.0
	float okEnemies = 0.0
	float okMovement = 0.0
	float okWallRun = 0.0
} file

void function BTVoice_Init()
{
	float now = Time()
	file.okLocation = now
	file.okTitan = now
	file.okHealth = now
	file.okBT = now
	file.okWeapon = now
	file.okEnemies = now
	file.okMovement = now
	file.okWallRun = now
	printt( "[BTVoice] started. Sending to " + BTVOICE_URL + ". If the app shows nothing, launch the game with -allowlocalhttp." )
	thread BTVoice_Loop()
}

void function BTVoice_Loop()
{
	wait 4.0 // let the level finish loading
	BTVoice_Tick()
	BTVoice_Send( "map_change", "The Pilot has arrived on the map " + GetMapName() + ".", BTVoice_Data() )
	while ( true )
	{
		wait BTVOICE_TICK
		BTVoice_Tick()
	}
}

void function BTVoice_Tick()
{
	array<entity> players = GetPlayerArray()
	if ( players.len() == 0 )
		return
	file.player = players[0]
	if ( !IsValid( file.player ) )
		return

	thread BTVoice_SenseTitan()
	thread BTVoice_SenseHealth()
	thread BTVoice_SenseBT()
	thread BTVoice_SenseLocation()
	thread BTVoice_SenseWeapon()
	thread BTVoice_SenseEnemies()
	thread BTVoice_SenseMovement()
	thread BTVoice_SenseWallRun()
	BTVoice_Publish()
}

// ---------------------------------------------------------------- sensors

void function BTVoice_SenseTitan()
{
	file.inTitan = file.player.IsTitan()
	file.okTitan = Time()
}

void function BTVoice_SenseHealth()
{
	int maxHealth = file.player.GetMaxHealth()
	if ( maxHealth > 0 )
		file.healthPct = int( 100.0 * file.player.GetHealth() / maxHealth )
	file.okHealth = Time()
}

void function BTVoice_SenseBT()
{
	file.btDistance = -1
	file.btHealthPct = -1
	if ( !file.inTitan )
	{
		entity bt = file.player.GetPetTitan()
		if ( IsAlive( bt ) )
		{
			file.btDistance = int( Distance( file.player.GetOrigin(), bt.GetOrigin() ) * 0.0254 ) // units are inches
			int maxHealth = bt.GetMaxHealth()
			if ( maxHealth > 0 )
				file.btHealthPct = int( 100.0 * bt.GetHealth() / maxHealth )
		}
	}
	file.okBT = Time()
}

// Indoors / outdoors has no direct flag in the game, so this looks upward:
// five rays fanned around straight up, counting how many hit something solid
// within about 15 m. Treat it as a good guess, not a guarantee.
void function BTVoice_SenseLocation()
{
	vector eye = file.player.EyePosition()
	array<vector> directions = [ < 0, 0, 1 >, < 0.5, 0, 1 >, < -0.5, 0, 1 >, < 0, 0.5, 1 >, < 0, -0.5, 1 > ]
	int covered = 0
	foreach ( vector direction in directions )
	{
		vector end = eye + Normalize( direction ) * BTVOICE_COVER_RANGE
		TraceResults trace = TraceLine( eye, end, [ file.player ], TRACE_MASK_SOLID, TRACE_COLLISION_GROUP_NONE )
		if ( trace.fraction < 1.0 )
			covered++
	}
	if ( covered >= 4 )
		file.location = "indoors"
	else if ( covered >= 1 )
		file.location = "under cover"
	else
		file.location = "outdoors"
	file.okLocation = Time()
}

void function BTVoice_SenseWeapon()
{
	entity weapon = file.player.GetActiveWeapon()
	file.weapon = ""
	if ( IsValid( weapon ) )
		file.weapon = weapon.GetWeaponClassName()
	file.okWeapon = Time()
}

void function BTVoice_SenseEnemies()
{
	vector origin = file.player.GetOrigin()
	int team = file.player.GetTeam()
	int enemies = 0
	int titans = 0
	foreach ( entity npc in GetNPCArray() )
	{
		if ( !IsAlive( npc ) || npc.GetTeam() == team )
			continue
		if ( DistanceSqr( npc.GetOrigin(), origin ) > BTVOICE_ENEMY_RANGE * BTVOICE_ENEMY_RANGE )
			continue
		enemies++
		if ( npc.IsTitan() )
			titans++
	}
	file.enemies = enemies
	file.enemyTitans = titans
	file.okEnemies = Time()
}

void function BTVoice_SenseMovement()
{
	file.onGround = file.player.IsOnGround()
	file.sliding = file.player.IsSliding()
	file.crouched = file.player.IsCrouched()
	file.okMovement = Time()
}

// separate from the other movement checks so a problem here can't hide them
void function BTVoice_SenseWallRun()
{
	file.wallRunning = file.player.IsWallRunning()
	file.okWallRun = Time()
}

// ------------------------------------------------------------- reporting

string function BTVoice_Action()
{
	if ( file.wallRunning )
		return "wallrunning"
	if ( file.sliding )
		return "sliding"
	if ( !file.onGround )
		return "airborne"
	if ( file.crouched )
		return "crouching"
	return "standing"
}

string function BTVoice_Bool( bool value )
{
	return value ? "true" : "false"
}

// every value here is a number, a true/false, or one of our own fixed words,
// so nothing needs JSON escaping
string function BTVoice_Data()
{
	float now = Time()
	array<string> failed = []
	if ( now - file.okTitan > BTVOICE_SENSOR_STALE ) failed.append( "titan" )
	if ( now - file.okHealth > BTVOICE_SENSOR_STALE ) failed.append( "health" )
	if ( now - file.okBT > BTVOICE_SENSOR_STALE ) failed.append( "bt" )
	if ( now - file.okLocation > BTVOICE_SENSOR_STALE ) failed.append( "location" )
	if ( now - file.okWeapon > BTVOICE_SENSOR_STALE ) failed.append( "weapon" )
	if ( now - file.okEnemies > BTVOICE_SENSOR_STALE ) failed.append( "enemies" )
	if ( now - file.okMovement > BTVOICE_SENSOR_STALE ) failed.append( "movement" )
	if ( now - file.okWallRun > BTVOICE_SENSOR_STALE ) failed.append( "wallrun" )

	string errors = ""
	for ( int i = 0; i < failed.len(); i++ )
	{
		if ( i > 0 )
			errors += ","
		errors += "\"" + failed[i] + " sensor failed (see the game console)\""
	}

	string data = "{"
	data += "\"map\":\"" + GetMapName() + "\""
	data += ",\"location\":\"" + file.location + "\""
	data += ",\"in_titan\":" + BTVoice_Bool( file.inTitan )
	data += ",\"health_pct\":" + file.healthPct
	data += ",\"bt_distance_m\":" + file.btDistance
	data += ",\"bt_health_pct\":" + file.btHealthPct
	data += ",\"weapon\":\"" + file.weapon + "\""
	data += ",\"enemies_near\":" + file.enemies
	data += ",\"enemy_titans_near\":" + file.enemyTitans
	data += ",\"action\":\"" + BTVoice_Action() + "\""
	data += ",\"sensor_errors\":[" + errors + "]"
	data += "}"
	return data
}

void function BTVoice_Send( string eventType, string text, string data )
{
	string body = "{\"type\":\"" + eventType + "\",\"text\":\"" + text + "\",\"data\":" + data + "}"
	NSHttpPostBody( BTVOICE_URL, body )
	file.lastSend = Time()
}

void function BTVoice_Publish()
{
	bool alive = IsAlive( file.player )
	bool low = file.healthPct >= 0 && file.healthPct < BTVOICE_LOW_HEALTH

	// events, but never on the very first reading (that would be a false "embark")
	if ( file.haveBaseline )
	{
		if ( file.inTitan && !file.wasTitan )
			BTVoice_Send( "embark", "The Pilot has embarked into BT-7274.", BTVoice_Data() )
		else if ( !file.inTitan && file.wasTitan )
			BTVoice_Send( "disembark", "The Pilot has left the Titan and is on foot.", BTVoice_Data() )
		if ( low && !file.wasLow && alive )
			BTVoice_Send( "low_health", "The Pilot's health has dropped below " + BTVOICE_LOW_HEALTH + " percent.", BTVoice_Data() )
		if ( !alive && file.wasAlive )
			BTVoice_Send( "death", "The Pilot has been killed.", BTVoice_Data() )
	}
	file.haveBaseline = true
	file.wasTitan = file.inTitan
	file.wasLow = low
	file.wasAlive = alive

	// a state snapshot whenever something meaningful changed, plus a heartbeat
	string signature = file.location + "|" + BTVoice_Bool( file.inTitan ) + "|" + ( file.healthPct / 10 ) + "|" + file.enemies + "|" + file.enemyTitans + "|" + file.weapon + "|" + BTVoice_Action()
	float now = Time()
	bool changed = signature != file.lastSignature
	if ( ( changed && now - file.lastSend >= BTVOICE_MIN_GAP ) || now - file.lastSend >= BTVOICE_HEARTBEAT )
	{
		file.lastSignature = signature
		BTVoice_Send( "state", "state update", BTVoice_Data() )
	}
}
