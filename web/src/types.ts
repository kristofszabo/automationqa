export type ActionType = 'navigate' | 'click' | 'type' | 'assert';
export const ACTION_TYPES: ActionType[] = ['navigate', 'click', 'type', 'assert'];

interface BaseStep {
  step: number;
  action: ActionType;
  timestamp_ms: number;
}

export interface NavigateStep extends BaseStep { action: 'navigate'; url: string; }
export interface ClickStep    extends BaseStep { action: 'click';    selector: string; }
export interface TypeStep     extends BaseStep { action: 'type';     selector: string; value: string; }
export interface AssertStep   extends BaseStep { action: 'assert';   selector: string; expected: string; }

export type Step = NavigateStep | ClickStep | TypeStep | AssertStep;
