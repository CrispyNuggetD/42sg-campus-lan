#ifndef HEXWARS_H
# define HEXWARS_H

# define HW_API_VERSION 1
# define HW_MAX_CELLS 61
# define HW_MAX_PLAYERS 6
# define HW_NEUTRAL -1
# define HW_MAX_UNITS 99

/* Axial coordinates. Directions: E, NE, NW, W, SW, SE. */
typedef struct s_hw_cell
{
	int q;
	int r;
	int owner;
	int units;
	int neighbors[6]; /* cell indices; -1 means outside the map */
} t_hw_cell;

typedef struct s_hw_state
{
	int api_version;
	int turn;
	int me; /* player index 0..player_count-1, never a network ID */
	int player_count;
	int cell_count;
	int max_turns;
	t_hw_cell cells[HW_MAX_CELLS];
} t_hw_state;

typedef struct s_hw_attributes
{
	int growth;
	int attack;
	int armor; /* each 1..5; sum must equal 9 */
} t_hw_attributes;

typedef struct s_hw_action
{
	int from;
	int to;
	int units; /* zero = pass; otherwise leave at least one unit behind */
} t_hw_action;

/* Implement both. No main(), libc, OS calls, or external libraries. */
void bot_config(t_hw_attributes *attributes);
void bot_turn(const t_hw_state *state, t_hw_action *action);

#endif
